# SPDX-License-Identifier: AGPL-3.0-or-later
"""几何解析解与端到端回归；全部处理结果写入系统临时目录。

从项目根目录运行：python -m unittest discover -s tests -v
"""

from configparser import ConfigParser
import csv
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from examples.create_demo import create_demo
from lupa.config import load_config
from lupa.fractal import fractal_dimension
from lupa.mesh import Mesh, load_mesh, read_stl, repair_mesh, save_mesh
from lupa.metrics import cart2, pca_metrics, roughness, shape_variance, size_metrics
from lupa.pipeline import FIELDS, run_pipeline


PROJECT = Path(__file__).resolve().parents[1]
ALL_METRICS = ('equivalent', 'wadell', 'pca', 'shape', 'roughness', 'fractal', 'filter_fractal')


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='lupa_regression_')
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        parser = ConfigParser(interpolation=None)
        parser.read(PROJECT / 'analysis.ini', encoding='utf-8-sig')
        directories = {
            ('RepairStl', 'InputDir'): 'input',
            ('RepairStl', 'OutputDir'): 'output/stl/repaired',
            ('FilterStl', 'OutputDir'): 'output/stl/filtered',
            ('Analysis', 'InputDirRepair'): 'output/mesh/repaired',
            ('Analysis', 'InputDirFilter'): 'output/mesh/filtered',
            ('Analysis', 'OutputDirResult'): 'output/results',
            ('Display', 'OutputDirRepair'): 'output/images/repaired',
            ('Display', 'OutputDirFilter'): 'output/images/filtered',
        }
        for (section, key), value in directories.items():
            parser[section][key] = value
        config_path = self.root / 'analysis.ini'
        with config_path.open('w', encoding='utf-8') as stream:
            parser.write(stream)
        self.settings = replace(load_config(config_path), workers=1, export='png',
                                voxel_size=0.003, radii=(0.003, 0.006, 0.009))

    def test_analytic_geometry_and_standard_deviation(self):
        vertices = np.array([[0, 0, 0], [4, 0, 0], [0, 2, 0], [0, 0, 1]], float)
        faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
        # 直角四面体 V=abc/6，其四个三角形面积可以直接求得。
        volume, area = 4 / 3, 7 + np.sqrt(21)
        expected = ((6 * volume / np.pi) ** (1 / 3), area / volume,
                    np.pi ** (1 / 3) * (6 * volume) ** (2 / 3) / area)
        np.testing.assert_allclose(size_metrics(vertices, faces), expected, atol=1e-12)
        np.testing.assert_allclose(size_metrics(vertices + [10, 20, 30], faces), expected, atol=1e-12)
        axes = [[3, 0, 0], [-3, 0, 0], [0, 2, 0], [0, -2, 0], [0, 0, 1], [0, 0, -1]]
        np.testing.assert_allclose(pca_metrics(axes), (2 / 3, 1 / 2, 1 / 3), atol=1e-12)
        self.assertEqual(shape_variance([[1, 0, 0], [3, 0, 0]]), 2)
        ra, rz, distances = roughness([[0.2, 0.2, 2], [0.3, 0.3, 2]], [],
                                     [[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]])
        np.testing.assert_array_equal(distances, [2, 2])
        self.assertEqual(ra, 2)
        self.assertEqual(rz, 0)  # 此处为标准差，不能换成均方根 2。

    def test_cartesian_to_spherical_coordinates(self):
        vertices = np.array([[1, 0, 0], [0, 2, 0], [0, 0, 3], [-4, 0, 0]], float)
        azimuth, elevation, radius, variance = cart2(*vertices.T)
        np.testing.assert_allclose(azimuth, [0, np.pi / 2, 0, np.pi], atol=1e-15)
        np.testing.assert_allclose(elevation, [0, 0, np.pi / 2, 0], atol=1e-15)
        np.testing.assert_array_equal(radius, [1, 2, 3, 4])
        self.assertAlmostEqual(variance, 5 / 3)
        self.assertEqual(variance, shape_variance(vertices))
        self.assertEqual(cart2(3, 4, 0)[2:], (5, 0))

    def test_repair_removes_internal_component_and_preserves_origin(self):
        paths = create_demo(self.settings.input_dir, points=200)
        raw = read_stl(paths[0])
        repaired = repair_mesh(raw, center=True)
        self.assertEqual(len(raw.faces), 400)
        self.assertEqual(len(repaired.faces), 396)
        self.assertEqual(len(repaired.vertices), 200)
        restored = repaired.vertices + repaired.origin
        radii = np.linalg.norm(restored - [0.10, 0.08, 0.05], axis=1)
        np.testing.assert_allclose(radii, 0.03, atol=1e-14)
        np.testing.assert_allclose(repaired.vertices[repaired.faces].mean(axis=(0, 1)), 0, atol=1e-14)

    def test_full_pipeline_and_parallel_agreement(self):
        create_demo(self.settings.input_dir, points=200)
        settings = replace(self.settings, metrics=ALL_METRICS)
        progress = []
        result = run_pipeline(settings, lambda done, total, name: progress.append((done, total, name)))
        self.assertEqual(len(result.rows), 3)
        self.assertEqual([entry[:2] for entry in progress], [(1, 3), (2, 3), (3, 3)])
        with result.csv_path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, ['name', *FIELDS])
            self.assertEqual(len(list(reader)), 3)
        metadata = json.loads(result.json_path.read_text(encoding='utf-8'))
        self.assertEqual(metadata['fields'], list(FIELDS))
        self.assertEqual(metadata['enabled_metrics'], list(ALL_METRICS))
        for row in result.rows:
            self.assertEqual(set(row), {'name', *FIELDS})
            self.assertTrue(np.isfinite([row[field] for field in FIELDS]).all())
            self.assertGreater(row['d_v'], 0)
            self.assertGreater(row['SSA'], 0)
            self.assertGreater(row['Wadell'], 0)
            self.assertLessEqual(row['Wadell'], 1 + 1e-10)
            for label in ('EI', 'FI', 'AR'):
                self.assertGreater(row[label], 0)
                self.assertLessEqual(row[label], 1)
            name = Path(row['name']).stem
            repaired = load_mesh(settings.repair_mesh_dir / row['name'])
            filtered_name = name.removesuffix('_obj') + '_filter_' + settings.tag + '_obj.npz'
            filtered = load_mesh(settings.filter_mesh_dir / filtered_name)
            self.assertLess(len(filtered.faces), len(repaired.faces))
            np.testing.assert_array_equal(filtered.origin, repaired.origin)
            png = settings.repair_image_dir / (name + '.png')
            self.assertEqual(png.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
        artifacts = list(settings.result_dir.glob('*_fractal.npz'))
        self.assertEqual(len(artifacts), 6)
        for artifact in artifacts:
            with np.load(artifact) as fit:
                self.assertEqual(float(fit['voxel_size']), settings.voxel_size)
                self.assertTrue(np.all(np.diff(fit['V_mm3']) >= 0))
        parallel = run_pipeline(replace(settings, workers=2), stage='analyze')
        self.assertEqual([row['name'] for row in result.rows], [row['name'] for row in parallel.rows])
        for serial_row, parallel_row in zip(result.rows, parallel.rows):
            np.testing.assert_allclose([serial_row[field] for field in FIELDS],
                                       [parallel_row[field] for field in FIELDS], atol=1e-12, rtol=1e-12)

    def test_name_pairing_and_different_coordinate_origins(self):
        settings = replace(self.settings, metrics=('roughness',))
        settings.repair_mesh_dir.mkdir(parents=True)
        settings.filter_mesh_dir.mkdir(parents=True)
        physical = np.array([[0, 0, 0], [4, 0, 0], [0, 2, 0], [0, 0, 1]], float) * 0.001
        physical += [0.01, 0.02, 0.03]
        faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
        repair_origin = np.array([0.01, 0.02, 0.03])
        filter_origin = repair_origin + [0.004, -0.001, 0.003]
        repaired = Mesh(physical - repair_origin, faces, repair_origin)
        filtered = Mesh(physical - filter_origin, faces, filter_origin)
        save_mesh(repaired, settings.repair_mesh_dir / 'sample_repair_obj.npz')
        save_mesh(filtered, settings.filter_mesh_dir / f'sample_repair_filter_{settings.tag}_obj.npz')
        wrong = Mesh(filtered.vertices + 10, faces, filter_origin)
        save_mesh(wrong, settings.filter_mesh_dir / 'aaa_residual_obj.npz')
        save_mesh(wrong, settings.filter_mesh_dir / 'sample_repair_filter_old_obj.npz')
        result = run_pipeline(settings, stage='analyze')
        self.assertEqual(len(result.rows), 1)
        row = result.rows[0]
        self.assertEqual(row['name'], 'sample_repair_obj.npz')
        self.assertLess(abs(row['Ra']), 1e-14)
        self.assertLess(abs(row['Rz']), 1e-14)
        self.assertTrue(all(row[field] == 0 for field in FIELDS if field not in ('Ra', 'Rz')))

    def test_fractal_small_grid_and_translation_invariance(self):
        vertices = np.array([[0, 0, 0], [0.004, 0, 0], [0, 0.002, 0], [0, 0, 0.001]])
        first = fractal_dimension(vertices, 0.0002, [0.0002, 0.0005, 0.0006, 0.001])
        second = fractal_dimension(vertices + [0.01, 0.02, 0.03], 0.0002,
                                   [0.0002, 0.0005, 0.0006, 0.001])
        self.assertEqual(first['voxel_size'], 0.0002)
        np.testing.assert_allclose(first['V_mm3'], second['V_mm3'], rtol=1e-12)
        # 独立 MATLAB R2023b 对照得到的体积基准，按长度单位缩放为 mm。
        np.testing.assert_allclose(first['V_mm3'], [2.528e-9, 12.832e-9, 12.832e-9, 32.688e-9], rtol=1e-12)
        self.assertAlmostEqual(first['D'], 1.4258392786569873, places=12)


if __name__ == '__main__':
    unittest.main()

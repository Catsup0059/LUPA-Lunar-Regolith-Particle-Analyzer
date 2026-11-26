# SPDX-License-Identifier: AGPL-3.0-or-later
"""生成确定性合成示例，所有网格均非真实月壤扫描数据。

球体、椭球及起伏颗粒用于演示读取、连通表面提取、简化、分析和绘图。
坐标单位为 mm；球体内部附加一个独立小四面体，用于演示内部表面剔除。
"""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial import ConvexHull

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lupa.mesh import Mesh, write_stl


def _directions(count):
    """Fibonacci 球面采样，不依赖随机数种子。"""
    index = np.arange(count, dtype=float)
    height = 1 - 2 * (index + 0.5) / count
    longitude = index * np.pi * (3 - np.sqrt(5))
    radial = np.sqrt(1 - height ** 2)
    return np.column_stack((radial * np.cos(longitude), radial * np.sin(longitude), height))


def _outward_faces(vertices, center):
    faces = ConvexHull(vertices).simplices.copy()
    triangles = vertices[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    inward = np.einsum('ij,ij->i', normals, triangles.mean(axis=1) - center) < 0
    faces[inward] = faces[inward][:, [0, 2, 1]]
    return faces


def create_demo(output_dir=None, points=240):
    """写入三个示例 STL 和生成参数，返回 STL 文件列表。"""
    output_dir = Path(output_dir) if output_dir is not None else Path(__file__).parent / 'stl'
    output_dir.mkdir(parents=True, exist_ok=True)
    directions = _directions(points)
    center = np.array([0.10, 0.08, 0.05])
    faces = _outward_faces(directions, np.zeros(3))

    sphere = directions * 0.03 + center
    inner = np.array([[1, 1, 1], [-1, -1, 1], [-1, 1, -1], [1, -1, -1]]) * 0.001
    inner_faces = _outward_faces(inner, np.zeros(3)) + points
    sphere_with_inner = Mesh(np.vstack((sphere, inner + center)), np.vstack((faces, inner_faces)))

    ellipsoid = Mesh(directions * [0.036, 0.025, 0.020] + center, faces.copy())
    longitude = np.arctan2(directions[:, 1], directions[:, 0])
    latitude = np.arcsin(directions[:, 2])
    radius = 0.029 * (
        1 + 0.10 * np.sin(5 * longitude) * np.cos(3 * latitude)
        + 0.05 * np.cos(7 * longitude) * np.cos(latitude)
    )
    # 保留球面的连通关系，允许表面起伏形成局部凹凸，而非再次取凸包。
    rough_particle = Mesh(directions * radius[:, None] + center, faces.copy())
    meshes = {
        'demo_sphere': sphere_with_inner,
        'demo_ellipsoid': ellipsoid,
        'demo_rough_particle': rough_particle,
    }
    paths = []
    records = []
    for name, mesh in meshes.items():
        path = output_dir / (name + '.stl')
        write_stl(mesh, path)
        paths.append(path)
        records.append({'file': path.name, 'vertices': len(mesh.vertices), 'faces': len(mesh.faces)})
    manifest = {
        'data_type': 'deterministic synthetic demonstration meshes; not measured lunar regolith',
        '说明': '确定性合成测试网格，非真实月壤扫描数据，不用于形成科学结论。',
        'coordinate_unit': 'mm',
        'surface_points': points,
        'center_mm': center.tolist(),
        'sphere_radius_mm': 0.03,
        'ellipsoid_semiaxes_mm': [0.036, 0.025, 0.020],
        'sphere_internal_component': 'independent tetrahedron, removed by largest-area component selection',
        'meshes': records,
    }
    (output_dir / 'synthetic_data.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    return paths


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='生成非真实月壤的合成演示 STL')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'stl')
    parser.add_argument('--points', type=int, default=240)
    args = parser.parse_args()
    for generated in create_demo(args.output, args.points):
        print(generated)

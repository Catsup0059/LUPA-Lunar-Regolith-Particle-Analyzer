"""网格格式、最大连通组件和坐标配准的回归检查。"""

from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np
from numpy.testing import assert_allclose, assert_array_equal
from scipy.io import savemat
from scipy.spatial import ConvexHull

from lupa.mesh import Mesh, clean_mesh, filter_mesh, load_mesh
from lupa.mesh import read_stl, repair_mesh, save_mesh, write_stl


def tetrahedron(scale=1, translation=(0, 0, 0)):
    vertices = np.array([[0, 0, 0], [4, 0, 0], [0, 2, 0], [0, 0, 1]], dtype=float)
    faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    return Mesh(vertices * scale + translation, faces)


class MeshTests(unittest.TestCase):
    def test_ascii_and_binary_stl(self):
        mesh = tetrahedron(translation=(10, 20, 30))
        with tempfile.TemporaryDirectory() as folder:
            ascii_path = Path(folder) / "颗粒 ascii.stl"
            write_stl(mesh, ascii_path)
            loaded = read_stl(ascii_path)
            assert_allclose(loaded.vertices[loaded.faces], mesh.vertices[mesh.faces])
            header = b"solid binary file with misleading header".ljust(80, b"\0")
            data = bytearray(header + struct.pack("<I", len(mesh.faces)))
            for triangle in mesh.vertices[mesh.faces]:
                data.extend(struct.pack("<12fH", *np.zeros(3), *triangle.ravel(), 0))
            binary_path = Path(folder) / "binary.stl"
            binary_path.write_bytes(data)
            binary = read_stl(binary_path)
            assert_allclose(binary.vertices[binary.faces], mesh.vertices[mesh.faces])

    def test_removes_duplicate_and_zero_area_faces(self):
        mesh = tetrahedron()
        vertices = np.vstack((mesh.vertices, mesh.vertices[0], [2, 0, 0]))
        faces = np.vstack((mesh.faces, [4, 2, 1], [0, 4, 1], [0, 5, 1]))
        cleaned = clean_mesh(Mesh(vertices, faces))
        self.assertEqual(cleaned.vertices.shape, (4, 3))
        self.assertEqual(cleaned.faces.shape, (4, 3))

    def test_largest_surface_and_shared_origin(self):
        outer = tetrahedron(translation=(10, 20, 30))
        inner = tetrahedron(0.1, (10.2, 20.2, 30.2))
        combined = Mesh(
            np.vstack((outer.vertices, inner.vertices)),
            np.vstack((outer.faces, inner.faces + 4)),
        )
        repaired = repair_mesh(combined)
        self.assertEqual(len(repaired.faces), 4)
        assert_allclose(repaired.vertices[repaired.faces].mean(axis=(0, 1)), 0, atol=1e-14)
        assert_allclose(
            repaired.vertices[repaired.faces] + repaired.origin,
            outer.vertices[outer.faces],
        )
        uncentered = repair_mesh(combined, center=False)
        assert_allclose(uncentered.vertices[uncentered.faces], outer.vertices[outer.faces])
        assert_array_equal(uncentered.origin, np.zeros(3))

    def test_npz_and_mat_roundtrip(self):
        mesh = repair_mesh(tetrahedron(translation=(10, 20, 30)))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "particle.npz"
            save_mesh(mesh, path)
            loaded = load_mesh(path)
            assert_allclose(loaded.vertices, mesh.vertices)
            assert_array_equal(loaded.faces, mesh.faces)
            assert_allclose(loaded.origin, mesh.origin)
            mat_path = Path(folder) / "legacy.mat"
            savemat(mat_path, {
                "vertices": mesh.vertices, "faces": mesh.faces + 1, "origin": mesh.origin
            })
            loaded = load_mesh(mat_path)
            assert_allclose(loaded.vertices, mesh.vertices)
            assert_array_equal(loaded.faces, mesh.faces)
            assert_allclose(loaded.origin, mesh.origin)

    def test_filter_preserves_coordinate_frame(self):
        mesh = repair_mesh(tetrahedron(translation=(10, 20, 30)))
        filtered = filter_mesh(mesh, 1.0)
        assert_allclose(filtered.origin, mesh.origin)
        assert_allclose(filtered.vertices[filtered.faces], mesh.vertices[mesh.faces])

    def test_filter_reduces_surface_faces(self):
        vertices = np.random.default_rng(7).normal(size=(100, 3))
        vertices /= np.linalg.norm(vertices, axis=1)[:, None]
        faces = ConvexHull(vertices).simplices.copy()
        triangles = vertices[faces]
        normals = np.cross(
            triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
        )
        inward = np.sum(normals * triangles.mean(axis=1), axis=1) < 0
        faces[inward] = faces[inward, ::-1]
        mesh = Mesh(vertices, faces, [10, 20, 30])
        filtered = filter_mesh(mesh, 0.5)
        self.assertLessEqual(len(filtered.faces), len(mesh.faces) // 2)
        self.assertGreater(len(filtered.faces), 0)
        assert_allclose(filtered.origin, mesh.origin)


if __name__ == "__main__":
    unittest.main()

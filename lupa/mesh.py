# SPDX-License-Identifier: AGPL-3.0-or-later
"""STL 网格读写、连通表面提取和简化。

网格在本模块中使用从 0 开始的面索引。vertices + origin 表示输入
坐标系中的顶点；简化阶段继承该坐标系，不对两份网格分别居中。
"""

from dataclasses import dataclass, field
from pathlib import Path
import struct

import numpy as np
from scipy import sparse
from scipy.io import loadmat
from scipy.sparse.csgraph import connected_components


@dataclass
class Mesh:
    """三角网格及其相对于输入坐标系的平移量。"""

    vertices: np.ndarray
    faces: np.ndarray
    origin: np.ndarray = field(default_factory=lambda: np.zeros(3))

    def __post_init__(self):
        self.vertices = np.asarray(self.vertices, dtype=np.float64)
        self.faces = np.asarray(self.faces, dtype=np.int64)
        self.origin = np.asarray(self.origin, dtype=np.float64).reshape(3)


def clean_mesh(mesh):
    """合并重合顶点，删除索引顺序相同的重复面和零面积面，移除未引用顶点。"""
    vertices, first, inverse = np.unique(
        mesh.vertices, axis=0, return_index=True, return_inverse=True
    )
    order = np.argsort(first)
    renumber = np.empty(len(order), dtype=np.int64)
    renumber[order] = np.arange(len(order))
    vertices = vertices[order]
    faces = renumber[inverse[mesh.faces]]
    _, first_face = np.unique(faces, axis=0, return_index=True)
    faces = faces[np.sort(first_face)]
    corners = vertices[faces]
    cross_product = np.cross(
        corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0]
    )
    faces = faces[np.any(cross_product != 0, axis=1)]
    used, compact_faces = np.unique(faces, return_inverse=True)
    return Mesh(vertices[used], compact_faces.reshape(-1, 3), mesh.origin.copy())


def read_stl(path):
    """读取 ASCII 或二进制 STL，保留文件中的坐标位置。

    二进制格式按 80 字节头、4 字节面数和每面 50 字节记录识别，
    包括以 solid 开头的二进制文件。
    """
    data = Path(path).read_bytes()
    binary = False
    if len(data) >= 84:
        face_count = struct.unpack_from("<I", data, 80)[0]
        binary = len(data) == 84 + 50 * face_count
    if binary:
        record_type = np.dtype([
            ("normal", "<f4", (3,)),
            ("vertices", "<f4", (3, 3)),
            ("attribute", "<u2"),
        ])
        records = np.frombuffer(data, dtype=record_type, offset=84)
        vertices = records["vertices"].reshape(-1, 3).astype(np.float64)
    else:
        rows = []
        for line in data.decode("utf-8-sig").splitlines():
            fields = line.split()
            if fields and fields[0].lower() == "vertex":
                rows.append(fields[1:4])
        vertices = np.asarray(rows, dtype=np.float64).reshape(-1, 3)
    faces = np.arange(len(vertices), dtype=np.int64).reshape(-1, 3)
    return clean_mesh(Mesh(vertices, faces))


def write_stl(mesh, path):
    """以 ASCII STL 输出当前局部坐标；origin 由 NPZ 中间文件保存。"""
    triangles = mesh.vertices[mesh.faces]
    normals = np.cross(
        triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    )
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    with Path(path).open("w", encoding="ascii", newline="\n") as stream:
        stream.write("solid LUPA\n")
        for normal, triangle in zip(normals, triangles):
            stream.write("  facet normal " + " ".join(f"{v:.17g}" for v in normal) + "\n")
            stream.write("    outer loop\n")
            for vertex in triangle:
                stream.write("      vertex " + " ".join(f"{v:.17g}" for v in vertex) + "\n")
            stream.write("    endloop\n  endfacet\n")
        stream.write("endsolid LUPA\n")


def repair_mesh(mesh, center=True):
    """保留表面积最大的连通表面，并按配置将其面顶点均值移到原点。

    此操作去除独立的内部孔隙表面；它不承担补洞或重建非流形网格。
    """
    mesh = clean_mesh(mesh)
    faces = mesh.faces
    edges = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    graph = sparse.coo_matrix(
        (np.ones(len(edges)), (edges[:, 0], edges[:, 1])),
        shape=(len(mesh.vertices), len(mesh.vertices)),
    ).tocsr()
    _, components = connected_components(graph, directed=False)
    triangles = mesh.vertices[faces]
    areas = 0.5 * np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]),
        axis=1,
    )
    face_components = components[faces[:, 0]]
    component_areas = np.bincount(face_components, weights=areas)
    faces = faces[face_components == np.argmax(component_areas)]
    used, indices = np.unique(faces, return_inverse=True)
    vertices = mesh.vertices[used].copy()
    faces = indices.reshape(-1, 3)
    origin = mesh.origin.copy()
    if center:
        offset = vertices[faces].mean(axis=(0, 1))
        vertices -= offset
        origin += offset
    return Mesh(vertices, faces, origin)


def filter_mesh(mesh, percent):
    """通过 PyMeshLab 的二次误差边折叠按目标面数比例简化网格。"""
    import pymeshlab

    meshes = pymeshlab.MeshSet()
    meshes.add_mesh(pymeshlab.Mesh(vertex_matrix=mesh.vertices, face_matrix=mesh.faces))
    meshes.meshing_decimation_quadric_edge_collapse(targetperc=float(percent))
    result = meshes.current_mesh()
    return Mesh(
        result.vertex_matrix().copy(), result.face_matrix().copy(), mesh.origin.copy()
    )


def save_mesh(mesh, path):
    """将顶点、面和坐标原点保存到 NPZ 中间文件。"""
    np.savez_compressed(
        path, vertices=mesh.vertices, faces=mesh.faces, origin=mesh.origin
    )


def load_mesh(path):
    """读取 NPZ 中间数据，或带有 origin 的旧 MATLAB MAT 网格。"""
    path = Path(path)
    if path.suffix.lower() == ".mat":
        data = loadmat(path)
        return Mesh(data["vertices"], data["faces"].astype(np.int64) - 1, data["origin"])
    with np.load(path, allow_pickle=False) as data:
        return Mesh(data["vertices"], data["faces"], data["origin"])

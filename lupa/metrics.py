# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Lu Zhang
"""颗粒尺寸、形态和粗糙度计算，面片索引统一从 0 开始。

延续原 MATLAB 程序的指标定义；Rz 表示距离的样本标准差。
输入坐标采用同一长度单位，粗糙度比较的两份网格采用同一坐标系。
"""

import numpy as np
from scipy.spatial import cKDTree


def size_metrics(vertices, faces):
    """返回等效体积直径、比表面积和 Wadell 球形度。

体积按定向三角面与坐标原点形成的四面体有符号体积求和。
输入为闭合且面片方向一致的三角网格。
"""
    vertices = np.asarray(vertices, dtype=float)
    faces = np.asarray(faces, dtype=np.int64)
    triangles = vertices[faces]
    first, second, third = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    area = 0.5 * np.linalg.norm(
        np.cross(second - first, third - first), axis=1
    ).sum()
    volume = abs(np.einsum("ij,ij->i", first, np.cross(second, third)).sum() / 6)
    diameter = (6 * volume / np.pi) ** (1 / 3)
    specific_area = area / volume
    sphericity = np.pi ** (1 / 3) * (6 * volume) ** (2 / 3) / area
    return float(diameter), float(specific_area), float(sphericity)


def pca_metrics(vertices):
    """将点云投影到 PCA 主轴，以轴向跨度计算 EI、FI、AR。"""
    vertices = np.asarray(vertices, dtype=float)
    centered = vertices - vertices.mean(axis=0)
    _, _, axes = np.linalg.svd(centered, full_matrices=False)
    score = centered @ axes.T
    longest, intermediate, shortest = np.sort(np.ptp(score, axis=0))[::-1]
    return (
        float(intermediate / longest),
        float(shortest / intermediate),
        float(shortest / longest),
    )


def cart2(x, y, z):
    """返回逐点方位角、仰角、半径及半径样本方差；角度单位为弧度。"""
    horizontal = np.hypot(x, y)
    radius = np.hypot(horizontal, z)
    elevation = np.arctan2(z, horizontal)
    azimuth = np.arctan2(y, x)
    # 单样本方差按 MATLAB var 的定义返回 0。
    variance = np.sum((radius - radius.mean()) ** 2) / max(radius.size - 1, 1)
    return azimuth, elevation, radius, float(variance)


def shape_variance(vertices):
    """返回相对于当前坐标原点的径向距离样本方差。"""
    vertices = np.asarray(vertices, dtype=float)
    return cart2(vertices[:, 0], vertices[:, 1], vertices[:, 2])[3]


def point_triangle_distance(point, first, second, third):
    """按三角形的顶点、边和面内区域求最近点与欧氏距离。"""
    ab = second - first
    ac = third - first
    ap = point - first
    d1 = np.dot(ab, ap)
    d2 = np.dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        closest = first
    else:
        bp = point - second
        d3 = np.dot(ab, bp)
        d4 = np.dot(ac, bp)
        if d3 >= 0 and d4 <= d3:
            closest = second
        else:
            vc = d1 * d4 - d3 * d2
            if vc <= 0 and d1 >= 0 and d3 <= 0:
                closest = first + (d1 / (d1 - d3)) * ab
            else:
                cp = point - third
                d5 = np.dot(ab, cp)
                d6 = np.dot(ac, cp)
                if d6 >= 0 and d5 <= d6:
                    closest = third
                else:
                    vb = d5 * d2 - d1 * d6
                    if vb <= 0 and d2 >= 0 and d6 <= 0:
                        closest = first + (d2 / (d2 - d6)) * ac
                    else:
                        va = d3 * d6 - d5 * d4
                        if va <= 0 and d4 - d3 >= 0 and d5 - d6 >= 0:
                            weight = (d4 - d3) / ((d4 - d3) + (d5 - d6))
                            closest = second + weight * (third - second)
                        else:
                            denominator = 1 / (va + vb + vc)
                            closest = first + ab * (vb * denominator) + ac * (vc * denominator)
    return float(np.linalg.norm(point - closest)), closest


def roughness(
    vertices_repair, faces_repair, vertices_filter, faces_filter, k=10, use_signed=False
):
    """返回平均绝对距离 Ra、距离样本标准差 Rz 和逐顶点距离。

对每个修复网格顶点，在滤波网格的 k 个近邻顶点关联面中搜索最近点。
faces_repair 保留在接口中，距离计算仅使用修复网格的顶点。
"""
    vertices_repair = np.asarray(vertices_repair, dtype=float)
    vertices_filter = np.asarray(vertices_filter, dtype=float)
    faces_filter = np.asarray(faces_filter, dtype=np.int64)
    count = min(k, len(vertices_filter))
    _, neighbors = cKDTree(vertices_filter).query(vertices_repair, k=count)
    neighbors = neighbors.reshape(len(vertices_repair), count)

    attachments = [[] for _ in vertices_filter]
    for face_index, face in enumerate(faces_filter):
        for vertex_index in face:
            attachments[vertex_index].append(face_index)

    distances = np.empty(len(vertices_repair), dtype=float)
    for index, point in enumerate(vertices_repair):
        candidate_faces = sorted(
            {face for vertex in neighbors[index] for face in attachments[vertex]}
        )
        closest = vertices_filter[neighbors[index, 0]]
        minimum = float(np.linalg.norm(point - closest))
        normal = np.zeros(3)
        if candidate_faces:
            minimum = np.inf
            for face_index in candidate_faces:
                triangle = vertices_filter[faces_filter[face_index]]
                distance, candidate = point_triangle_distance(point, *triangle)
                if distance < minimum:
                    minimum = distance
                    closest = candidate
                    normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
        if use_signed and np.linalg.norm(normal) > np.finfo(float).eps:
            minimum *= np.sign(np.dot(point - closest, normal))
        distances[index] = minimum

    ra = float(np.mean(np.abs(distances)))
    variance = np.sum((distances - distances.mean()) ** 2) / max(len(distances) - 1, 1)
    rz = float(np.sqrt(variance))
    return ra, rz, distances

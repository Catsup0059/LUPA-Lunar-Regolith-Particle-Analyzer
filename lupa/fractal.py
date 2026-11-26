# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Lu Zhang
"""通过表面体素化与 Minkowski 球形膨胀估算颗粒表面分形维数。"""

import warnings

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree


def _adaptive_radii(voxel_size, minimum_length, count=35):
    """沿用 MATLAB 版本的物理半径范围及对数间隔。"""
    lower = 2 * voxel_size
    upper = min(minimum_length / 4, 30 * voxel_size)
    if upper <= lower:
        upper = max(5 * voxel_size, 1.5 * lower)
    return np.exp(np.linspace(np.log(lower), np.log(upper), count))


def fractal_dimension(vertices, voxel_size=0.001, radii=None):
    """返回分形维数 D、拟合斜率、R²、半径、膨胀体积与计算记录。

坐标、voxel_size 和 radii 的单位均为 mm。voxel_size 可取 None、
空数组或 'auto'，由包围盒自动确定；radii 为空时自动生成 35 个半径。
体素化沿用“体素中心到最近顶点距离不超过 sqrt(3) 个体素”的近似。
"""
    vertices = np.asarray(vertices, dtype=float)
    min_voxel_size = 0.000014
    target_voxel_number = 350
    max_total_voxels = 5_000_000
    chunk_size = 1_000_000
    raw_min = vertices.min(axis=0)
    raw_max = vertices.max(axis=0)
    bbox_size = raw_max - raw_min
    valid_size = bbox_size[bbox_size > 0]
    characteristic_length = np.prod(valid_size) ** (1 / len(valid_size))
    minimum_length = valid_size.min()

    auto_voxel = (
        voxel_size is None
        or (isinstance(voxel_size, str) and voxel_size.lower() == 'auto')
        or np.size(voxel_size) == 0
    )
    auto_radius = radii is None or np.size(radii) == 0
    if auto_voxel:
        voxel_size = max(characteristic_length / target_voxel_number, min_voxel_size)
    else:
        voxel_size = float(voxel_size)

    # 自动体素模式逐次放大体素，直到总体素数满足上限。
    while True:
        if auto_radius:
            r_mm = _adaptive_radii(voxel_size, minimum_length)
        else:
            r_mm = np.asarray(radii, dtype=float).reshape(-1)
        pad_vox = int(np.ceil(r_mm.max() / voxel_size)) + 2
        pad_length = pad_vox * voxel_size
        min_v = raw_min - pad_length
        max_v = raw_max + pad_length
        shape = tuple(np.ceil((max_v - min_v) / voxel_size).astype(int))
        total_voxels = int(np.prod(shape))
        if total_voxels <= max_total_voxels:
            break
        if auto_voxel:
            voxel_size *= 1.25
        else:
            warnings.warn(
                f'固定体素大小产生 {total_voxels} 个体素；可增大体素或缩小最大半径。',
                RuntimeWarning,
                stacklevel=2,
            )
            break

    # 按 MATLAB ndgrid(:) 的列主序分块生成体素中心。
    tree = cKDTree(vertices)
    surface = np.empty(total_voxels, dtype=bool)
    threshold = np.sqrt(3) * voxel_size
    for start in range(0, total_voxels, chunk_size):
        stop = min(start + chunk_size, total_voxels)
        indices = np.column_stack(np.unravel_index(np.arange(start, stop), shape, order='F'))
        centers = min_v + voxel_size / 2 + indices * voxel_size
        nearest_distances, _ = tree.query(centers)
        surface[start:stop] = nearest_distances <= threshold
    surface = surface.reshape(shape, order='F')

    # 最近表面体素的欧氏距离 <= r_vox + 0.001，与原球形结构元素膨胀等价。
    # 半径为正，floor(x+0.5) 对应 MATLAB round，不使用 Python 的偶数舍入。
    voxel_distances = distance_transform_edt(~surface)
    voxel_radii = np.maximum(1, np.floor(r_mm / voxel_size + 0.5).astype(int))
    counts = np.array(
        [np.count_nonzero(voxel_distances <= radius + 0.001) for radius in voxel_radii]
    )
    volumes = counts * voxel_size ** 3
    log_radius = np.log(r_mm)
    log_volume = np.log(volumes)
    slope, intercept = np.polyfit(log_radius, log_volume, 1)
    fitted = slope * log_radius + intercept
    residual_sum = np.sum((log_volume - fitted) ** 2)
    total_sum = np.sum((log_volume - log_volume.mean()) ** 2)
    rsq = float(1 - residual_sum / total_sum) if total_sum != 0 else float('nan')
    dimension = float(3 - slope)

    logs = {
        'logr': log_radius,
        'logV': log_volume,
        'yfit': fitted,
        'slope': float(slope),
        'intercept': float(intercept),
        'Rsq': rsq,
        'voxelSize': voxel_size,
        'r_mm': r_mm,
        'V_mm3': volumes,
        'rawMin': raw_min,
        'rawMax': raw_max,
        'bboxSize': bbox_size,
        'Lchar': float(characteristic_length),
        'Lmin': float(minimum_length),
        'nx': shape[0],
        'ny': shape[1],
        'nz': shape[2],
        'totalVoxels': total_voxels,
        'padVox': pad_vox,
        'padLength': pad_length,
        'minVoxelSize': min_voxel_size,
        'targetVoxelNumber': target_voxel_number,
        'maxTotalVoxels': max_total_voxels,
    }
    return {
        'D': dimension,
        'slope': float(slope),
        'Rsq': rsq,
        'r_mm': r_mm,
        'V_mm3': volumes,
        'voxel_size': voxel_size,
        'logs': logs,
    }

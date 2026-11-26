"""导出颗粒网格及分形拟合图，不依赖 MATLAB 绘图。"""
# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from .mesh import Mesh


def mesh_figure(mesh: Mesh, title: str, shade: str = "solid", figure=None) -> Figure:
    if figure is None:
        figure = Figure(figsize=(6.8, 5.4), dpi=150, layout="constrained")
        FigureCanvasAgg(figure)
    axes = figure.add_subplot(111, projection="3d")
    vertices = mesh.vertices
    triangles = vertices[mesh.faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0],
                       triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    normals = np.divide(normals, lengths[:, None],
                        out=np.zeros_like(normals), where=lengths[:, None] != 0)
    light = np.array([0.35, -0.5, 0.8])
    light /= np.linalg.norm(light)
    brightness = 0.42 + 0.58 * np.abs(normals @ light)
    color = brightness[:, None] * np.array([0.52, 0.62, 0.73])
    collection = Poly3DCollection(
        triangles,
        facecolors="none" if shade == "mesh" else color,
        edgecolors="#334155" if shade in ("mesh", "both") else "none",
        linewidths=0.18,
    )
    axes.add_collection3d(collection)
    lower, upper = vertices.min(axis=0), vertices.max(axis=0)
    center = (lower + upper) / 2
    radius = (upper - lower).max() / 2
    axes.set_xlim(center[0] - radius, center[0] + radius)
    axes.set_ylim(center[1] - radius, center[1] + radius)
    axes.set_zlim(center[2] - radius, center[2] + radius)
    axes.set_box_aspect((1, 1, 1))
    axes.set(xlabel="X", ylabel="Y", zlabel="Z", title=title)
    axes.view_init(elev=24, azim=35)
    return figure


def save_mesh_image(mesh: Mesh, path: str | Path, shade: str = "solid") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure = mesh_figure(mesh, path.stem, shade)
    figure.savefig(path, dpi=150)
    figure.clear()


def save_fractal_plot(result: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure = Figure(figsize=(6.5, 4.5), dpi=150, layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots()
    logr = np.log(result["r_mm"])
    logv = np.log(result["V_mm3"])
    fit = np.polyfit(logr, logv, 1)
    axes.scatter(logr, logv, s=24, label="Dilation samples")
    axes.plot(logr, np.polyval(fit, logr), color="#b45309", label="Linear fit")
    axes.set(xlabel="ln(radius / mm)", ylabel="ln(volume / mm^3)",
             title=f'D = {result["D"]:.4f}    R² = {result["Rsq"]:.4f}')
    axes.legend()
    axes.grid(alpha=0.25)
    figure.savefig(path, dpi=150)
    figure.clear()


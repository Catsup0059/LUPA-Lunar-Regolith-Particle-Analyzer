"""组织修复、简化、指标计算与结果输出的批量处理流程。"""
# SPDX-License-Identifier: AGPL-3.0-or-later
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import csv
import json

import numpy as np

from . import __version__
from .config import Settings
from .mesh import read_stl, write_stl, repair_mesh, filter_mesh, save_mesh, load_mesh
from .metrics import size_metrics, pca_metrics, shape_variance, roughness
from .fractal import fractal_dimension
from .render import save_mesh_image, save_fractal_plot


FIELDS = ("d_v", "SSA", "Wadell", "EI", "FI", "AR", "shape_variance",
          "Ra", "Rz", "D_repair", "Rsq_repair", "D_filter", "Rsq_filter")


@dataclass
class RunResult:
    rows: list[dict]
    csv_path: Path | None
    json_path: Path | None


def preprocess_particle(path: Path, settings: Settings) -> Path:
    """在共同坐标系内完成修复和简化，保存可重复分析的网格。"""
    repaired = repair_mesh(read_stl(path), center=settings.center)
    filtered = filter_mesh(repaired, settings.fraction)
    base = path.stem + "_repair"
    filtered_base = base + "_filter_" + settings.tag
    write_stl(repaired, settings.repaired_dir / (base + ".stl"))
    write_stl(filtered, settings.filtered_dir / (filtered_base + ".stl"))
    repair_path = settings.repair_mesh_dir / (base + "_obj.npz")
    save_mesh(repaired, repair_path)
    save_mesh(filtered, settings.filter_mesh_dir / (filtered_base + "_obj.npz"))
    return repair_path


def analyze_particle(path: Path, settings: Settings) -> dict:
    """按颗粒名称和简化标记配对网格并计算所选指标。"""
    repaired = load_mesh(path)
    base = path.stem.removesuffix("_obj")
    filter_path = settings.filter_mesh_dir / (
        base + "_filter_" + settings.tag + "_obj" + path.suffix)
    filtered = load_mesh(filter_path)
    row = dict.fromkeys(FIELDS, 0.0)
    row["name"] = path.name
    enabled = settings.metrics
    if "equivalent" in enabled:
        row["d_v"], row["SSA"], _ = size_metrics(repaired.vertices, repaired.faces)
    if "wadell" in enabled:
        _, _, row["Wadell"] = size_metrics(filtered.vertices, filtered.faces)
    if "pca" in enabled:
        row["EI"], row["FI"], row["AR"] = pca_metrics(repaired.vertices)
    if "shape" in enabled:
        row["shape_variance"] = shape_variance(repaired.vertices)
    if "roughness" in enabled:
        vertices = filtered.vertices + filtered.origin - repaired.origin
        row["Ra"], row["Rz"], _ = roughness(
            repaired.vertices, repaired.faces, vertices, filtered.faces, k=settings.k)
    for flag, mesh, label in (("fractal", repaired, "repair"),
                              ("filter_fractal", filtered, "filter")):
        if flag in enabled:
            result = fractal_dimension(mesh.vertices, settings.voxel_size, settings.radii)
            row["D_" + label] = result["D"]
            row["Rsq_" + label] = result["Rsq"]
            prefix = settings.result_dir / (base + "_" + settings.tag + "_" + label + "_fractal")
            np.savez_compressed(str(prefix) + ".npz", r_mm=result["r_mm"],
                                V_mm3=result["V_mm3"], voxel_size=result["voxel_size"],
                                D=result["D"], slope=result["slope"], Rsq=result["Rsq"])
            save_fractal_plot(result, str(prefix) + ".png")
    return row


def display_particle(path: Path, settings: Settings) -> None:
    repaired = load_mesh(path)
    base = path.stem.removesuffix("_obj")
    filter_name = base + "_filter_" + settings.tag + "_obj"
    filtered = load_mesh(settings.filter_mesh_dir / (filter_name + path.suffix))
    if settings.export in ("png", "both"):
        save_mesh_image(repaired, settings.repair_image_dir / (path.stem + ".png"), settings.shade)
        save_mesh_image(filtered, settings.filter_image_dir / (filter_name + ".png"), settings.shade)
    if settings.export in ("screen", "both"):
        # 屏幕绘图在主进程执行。
        import matplotlib.pyplot as plt
        from .render import mesh_figure
        for mesh, title in ((repaired, path.stem), (filtered, filter_name)):
            figure = plt.figure(figsize=(6.8, 5.4), layout="constrained")
            mesh_figure(mesh, title, settings.shade, figure=figure)
        plt.show()


def _work(task: tuple[Path, Settings, str]) -> dict | None:
    path, settings, stage = task
    if stage in ("all", "preprocess"):
        path = preprocess_particle(path, settings)
    if stage in ("all", "analyze"):
        return analyze_particle(path, settings)
    return None


def _mesh_inputs(settings: Settings) -> list[Path]:
    """优先使用本版生成的 NPZ，也允许单独分析旧版 MAT 网格。"""
    paths = {p.stem: p for p in settings.repair_mesh_dir.glob("*_obj.mat")}
    paths.update({p.stem: p for p in settings.repair_mesh_dir.glob("*_obj.npz")})
    return [paths[key] for key in sorted(paths)]


def _export(rows: list[dict], settings: Settings) -> RunResult:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    prefix = settings.result_dir / (stamp + "_" + settings.tag + "_result")
    csv_path, json_path = prefix.with_suffix(".csv"), prefix.with_suffix(".json")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("name",) + FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    document = {
        "software": "LUPA", "version": __version__, "created": datetime.now().isoformat(),
        "enabled_metrics": list(settings.metrics), "fields": list(FIELDS),
        "coordinate_unit": "STL coordinate units; fractal coordinates and parameters: mm",
        "Rz_definition": "sample standard deviation of distances (ddof=1)",
        "disabled_metrics": "zero values are placeholders; consult enabled_metrics",
        "settings": asdict(settings), "particles": rows,
    }
    json_path.write_text(json.dumps(document, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return RunResult(rows, csv_path, json_path)


def run_pipeline(settings: Settings, progress=None, stage: str = "all") -> RunResult:
    for directory in (settings.repaired_dir, settings.filtered_dir, settings.repair_mesh_dir,
                      settings.filter_mesh_dir, settings.result_dir, settings.repair_image_dir,
                      settings.filter_image_dir):
        directory.mkdir(parents=True, exist_ok=True)
    if stage in ("all", "preprocess"):
        paths = sorted(p for p in settings.input_dir.iterdir() if p.suffix.lower() == ".stl")
    else:
        paths = _mesh_inputs(settings)
    tasks = [(path, settings, stage) for path in paths]
    rows = []
    if settings.workers == 1 or stage == "display":
        results = map(_work, tasks)
        for index, (path, row) in enumerate(zip(paths, results), 1):
            if row is not None:
                rows.append(row)
            if progress:
                progress(index, len(paths), path.name)
    else:
        with ProcessPoolExecutor(max_workers=settings.workers) as pool:
            for index, (path, row) in enumerate(zip(paths, pool.map(_work, tasks)), 1):
                if row is not None:
                    rows.append(row)
                if progress:
                    progress(index, len(paths), path.name)
    if stage in ("all", "display"):
        display_paths = ([settings.repair_mesh_dir / (p.stem + "_repair_obj.npz") for p in paths]
                         if stage == "all" else paths)
        for path in display_paths:
            display_particle(path, settings)
    return _export(rows, settings) if stage in ("all", "analyze") else RunResult([], None, None)


"""读取项目配置，所有相对路径均相对于 INI 所在目录。"""
# SPDX-License-Identifier: AGPL-3.0-or-later
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path


METRIC_OPTIONS = (
    ("EquivalentDiameter", "equivalent"),
    ("Wadell", "wadell"),
    ("PCA", "pca"),
    ("ShapeVariance", "shape"),
    ("Roughness", "roughness"),
    ("Fractal", "fractal"),
    ("FilterFractal", "filter_fractal"),
)


@dataclass
class Settings:
    input_dir: Path
    repaired_dir: Path
    filtered_dir: Path
    repair_mesh_dir: Path
    filter_mesh_dir: Path
    result_dir: Path
    repair_image_dir: Path
    filter_image_dir: Path
    fraction: float
    tag: str
    center: bool
    workers: int
    k: int
    metrics: tuple[str, ...]
    voxel_size: float | None
    radii: tuple[float, ...] | None
    shade: str
    export: str


def load_config(path: str | Path) -> Settings:
    path = Path(path).resolve()
    parser = ConfigParser(interpolation=None, inline_comment_prefixes=("#", ";"))
    with path.open(encoding="utf-8-sig") as stream:
        parser.read_file(stream)

    def directory(section: str, key: str) -> Path:
        return (path.parent / parser[section][key]).resolve()

    voxel = parser.get("Fractal", "VoxelSize", fallback="0.001")
    radii = parser.get("Fractal", "Radii", fallback="auto")
    return Settings(
        input_dir=directory("RepairStl", "InputDir"),
        repaired_dir=directory("RepairStl", "OutputDir"),
        filtered_dir=directory("FilterStl", "OutputDir"),
        repair_mesh_dir=directory("Analysis", "InputDirRepair"),
        filter_mesh_dir=directory("Analysis", "InputDirFilter"),
        result_dir=directory("Analysis", "OutputDirResult"),
        repair_image_dir=directory("Display", "OutputDirRepair"),
        filter_image_dir=directory("Display", "OutputDirFilter"),
        fraction=parser.getfloat("FilterStl", "Percent"),
        tag=parser["FilterStl"]["PercentDescription"],
        center=parser.getboolean("ImportObject", "ReshapeToCenter"),
        workers=parser.getint("Analysis", "Workers", fallback=1),
        k=parser.getint("Analysis", "Neighbors", fallback=10),
        metrics=tuple(key for option, key in METRIC_OPTIONS
                      if parser.getboolean("Analysis", option, fallback=(key == "roughness"))),
        voxel_size=None if voxel.lower() == "auto" else float(voxel),
        radii=None if radii.lower() == "auto" else tuple(float(x) for x in radii.split(",")),
        shade=parser.get("Display", "Shade", fallback="solid"),
        export=parser.get("Display", "Export", fallback="png"),
    )


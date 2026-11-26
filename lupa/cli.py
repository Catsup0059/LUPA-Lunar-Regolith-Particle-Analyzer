"""命令行与桌面入口参数。"""
# SPDX-License-Identifier: AGPL-3.0-or-later
import argparse
from dataclasses import replace
from pathlib import Path

from .config import load_config
from .pipeline import run_pipeline


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="LUPA 月壤颗粒形态与表面纹理分析")
    parser.add_argument("--config", type=Path,
                        default=Path(__file__).resolve().parents[1] / "analysis.ini")
    parser.add_argument("--stage", choices=("all", "preprocess", "analyze", "display"), default="all")
    parser.add_argument("--workers", type=int, help="覆盖配置中的并行进程数")
    parser.add_argument("--gui", action="store_true", help="打开桌面操作界面")
    args = parser.parse_args(argv)
    if args.gui:
        from .gui import run
        run(args.config)
        return
    settings = load_config(args.config)
    if args.workers is not None:
        settings = replace(settings, workers=args.workers)
    result = run_pipeline(settings, lambda done, total, name: print(f"[{done}/{total}] {name}"), args.stage)
    if result.csv_path:
        print(f"CSV: {result.csv_path}")
        print(f"JSON: {result.json_path}")


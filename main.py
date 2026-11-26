"""LUPA Python 主程序；--gui 启动桌面界面。"""
# SPDX-License-Identifier: AGPL-3.0-or-later
import multiprocessing

from lupa.cli import main


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()


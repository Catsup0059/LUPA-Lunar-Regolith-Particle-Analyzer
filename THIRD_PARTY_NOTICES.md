# Third-party notices

## LUPA license

LUPA source code is licensed under the GNU Affero General Public License v3.0 or later (`AGPL-3.0-or-later`). [LICENSE.txt](LICENSE.txt) and [license/LICENSE](license/LICENSE) contain identical copies of the full AGPL v3 text. Copyright and license notices appear in the source files.

The Python application uses the dependencies listed below. Each dependency retains its own copyright notices and license.

## Python dependencies

The versions in this table identify the distributions from which the included license copies were obtained. Installation version ranges are defined in [requirements.txt](requirements.txt).

| Dependency and version | Use in LUPA | License and copyright holders | Included license |
| --- | --- | --- | --- |
| NumPy 1.26.4 | Array operations, vector algebra, SVD, and NPZ storage | BSD 3-Clause; NumPy Developers | [numpy.txt](license/dependencies/numpy.txt) |
| SciPy 1.11.4 | Connected components, nearest-neighbor searches, distance transforms, and MAT import | BSD 3-Clause; Enthought, Inc. and SciPy Developers | [scipy.txt](license/dependencies/scipy.txt) |
| Matplotlib 3.10.3 | Mesh views, PNG export, and fractal-fit plots | Matplotlib license; Matplotlib Development Team and John D. Hunter | [matplotlib.txt](license/dependencies/matplotlib.txt) |
| PyMeshLab 2025.7.post1 | Quadric edge-collapse mesh simplification | GPL v3; PyMeshLab / MeshLab contributors | [pymeshlab.txt](license/dependencies/pymeshlab.txt) |

The license files are unchanged copies from the corresponding distributions. Additional NumPy, SciPy, and Matplotlib component licenses are included in [license/dependencies](license/dependencies). [manifest.json](license/dependencies/manifest.json) records each package version, original package-relative path, included copy, and SHA-256 checksum.

LUPA calls PyMeshLab's `meshing_decimation_quadric_edge_collapse` for mesh simplification. The implementations of PyMeshLab, NumPy, SciPy, and Matplotlib remain part of those projects. LUPA implements configuration handling, STL input/output, connected-surface selection, metric formulas, point-to-triangle distance calculations, voxel and radius organization, batch processing, result export, and the user interfaces.

Tkinter, `concurrent.futures`, `configparser`, and `argparse` are provided by the Python standard library. This repository distributes LUPA source code and license notices; dependency binaries and the Python interpreter are installed separately.

## Historical MATLAB dependencies

The earlier MATLAB workflow used **SPHARM-MAT v1.0.0**, developed by ShenLab at Indiana University under GPL v3 or later, and **point2trimesh**, by Daniel Frisch, under the BSD 3-Clause license. The Python application implements its STL handling and point-to-triangle distance calculations in `lupa/mesh.py` and `lupa/metrics.py`.

SPHARM-MAT, its NIfTI and Gipl components, and point2trimesh are not included or imported by this Python application. [license/GPL-3.0.txt](license/GPL-3.0.txt) preserves the full GPL v3 license text supplied with the historical SPHARM-MAT package.

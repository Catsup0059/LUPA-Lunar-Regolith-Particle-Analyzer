

# LUPA: Lunar Regolith Particle Analyzer

**LUPA** is a computational toolkit designed for the **batch and quantitative analysis of lunar regolith particle morphology**. 

**Coming soon:** the full codebase will be released after the paper is published.

<!-- PROJECT SHIELDS -->

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />

<p align="center">
  <a href="https://github.com/Catsup0059/LunarRegolithParticleAnalysis/tree/HPC_hit">
    <img src="LUPA1.png" alt="Logo" width="300" height="300">
  </a>

  <h3 align="center">LUPA：Lunar Regolith Particle Analyzer </h3>
  <p align="center">
    <br />
    <a href="https://github.com/shaojintian/Best_README_template"><strong>
</p>



 
## Contents

- [Overview](#Overview)
- [Installation](#Installation)
- [Inplementations](#Inplementations)
- [Results](#Results)
- [Contributors](#Contributors)
- [License](#License)
- [Aknowledgements](#Aknowledgements)

## Overview

Lunar regolith particle morphology plays a critical role in determining the mechanical and thermal properties of the lunar surface. However, many existing studies still rely primarily on qualitative observations, such as visual inspection of particle images or 3D reconstructions. Even when quantitative analysis is performed, the workflow often depends on specialized commercial morphology-analysis software, which limits transparency, reproducibility, and large-scale statistical analysis of particle populations.

To address these limitations, we developed LUPA, a computational toolkit for the batch analysis of lunar regolith particles derived from CT scans. The core contribution of LUPA lies in a systematic quantitative characterization framework, which extracts particle descriptors from two complementary perspectives: morphology and surface texture. The workflow begins with preprocessing of STL models, including mesh repair to remove internal pore structures captured during CT scanning and filtering to downsample particle point clouds. Based on the processed data, LUPA computes a set of quantitative features that capture both global shape characteristics and local surface complexity.

Built upon this characterization framework, LUPA further integrates a machine learning–based classification module, in which particles are categorized into four genetic types—glass, agglutinates, monominerals, and lithic fragments—using a support vector machine (SVM). Rather than being the primary focus, this classification module serves as a validation and application of the proposed morphological descriptors, demonstrating that particles of different origins occupy distinct and stable regions in the multidimensional feature space.

The combined analysis reveals that variations in particle type proportions are closely linked to regolith formation, space weathering processes, and maturity, while also exerting significant influence on macroscopic properties such as packing density, mechanical behavior, thermal conductivity, and optical characteristics. By integrating quantitative morphology analysis with data-driven classification, LUPA provides a transparent, reproducible, and extensible framework for both micro-scale characterization and macro-scale interpretation of lunar regolith.
  <p align="center">
    <img src="framework.png" alt="framework" width="510" height="500">
  </p>
</a>


## Installation

### 1. Get Code
```sh
git clone https://github.com/Catsup0059/LunarRegolithParticleAnalysis.git
```
### 2. Environment Preparation 

```sh
# create conda env for LUPA
conda create -n lupa python=3.12.7
conda activate lupa
# install pymeshlab
pip install pymeshlab
```

## Inplementations

### 1. Prepare Input Data
Place all particles STL files to be analyzed in the directory:
```sh
data/stl/original_stl
```
Each STL file should represent a single particle reconstructed from CT data.

### 2. Configure Parameters
The analysis parameters are defined in the configuration file analysis.ini.
Users are encouraged to modify parameters in this file rather than editing the  source code directly. Key parameters typically include:

• Output directory for saving analysis results

• Point cloud downsampling ratio used during preprocessing

• Other analysis-related settings

### 3. Run the Main Program
The entry point of the toolkit is `main.m`. Before running the program:

• Set the absolute path of the project root directory in the script.

• Configure the MATLAB parallel pool according to the available computational resources.

### 4. Excute Analysis
After the Configuration is completed, run:
```sh
main
```
The program will automatically process all STL files in the input directory, perform preprocessing, and extract particle morphology and surface texture descriptors.
All analysis results will be saved in:
```sh
data/result
```

## Result
 Representative results are provided to illustrate the capabilities of the toolkit. First, STL models reconstructed from particle scans are visualized as the input geometry for subsequent analysis. The effects of mesh simplification are demonstrated through different levels of STL downsampling, showing the trade-off between geometric detail and computational efficiency. In addition, spherical harmonic fitting with different harmonic orders is applied to the particle surfaces, illustrating how higher orders progressively capture finer geometric features.

Beyond single-particle examples, the toolkit is applied to several hundred particles segmented from CT data. Using the developed algorithms, texture features and morphological descriptors are automatically extracted and statistically summarized, providing quantitative insights into particle surface characteristics and shape distributions across the dataset.

Furthermore, based on the extracted morphological features, a support vector machine (SVM) classifier is employed to categorize particles into genetic types. Considering the high morphological similarity between monomineral grains and lithic fragments, these two categories are merged into a single class, resulting in three effective classes: glass, agglutinates, and mineral/lithic particles. The classification results demonstrate clear separability in the multidimensional feature space, and the overall classification accuracy exceeds 94%. This outcome further validates the effectiveness of the proposed quantitative descriptors and highlights the capability of the toolkit to support data-driven particle classification and origin analysis.
 
  <p align="center">
    <img src="result.png" alt="framework" width="510" height="500">
  </p>
</a>




## Contributors

请阅读**CONTRIBUTING.md** 查阅为该项目做出贡献的开发者。



## License

This project is licensed under the GNU Affero General Public License v3.0.

You may redistribute and modify this software under the terms of the
AGPL-3.0 license as published by the Free Software Foundation.

If you use this software in a network service, you must provide users
access to the corresponding source code as required by AGPL-3.0.

See the LICENSE file for the full license text. [LICENSE.txt](https://github.com/Catsup0059/LunarRegolithParticleAnalysis/blob/main/license/LICENSE)

## Aknowledgements
This project incorporates functionality from the Spherical Harmonic Modeling and Analysis Toolkit(SPHARM-MAT-v1-0-0), developed by ShenLab, Center for Neuroimaging, Indiana University. We gratefully acknowledge the efforts of the original developers and maintainers of this package. Their work has provided an important foundation for the development of this project.

The original source code and license of the package are preserved in this repository in accordance with the GNU Affero General Public License v3.0. We sincerely thank the authors for releasing their work as open-source software and supporting the advancement of the research community.



<!-- links -->
[your-project-path]:shaojintian/Best_README_template
[contributors-shield]: https://img.shields.io/github/contributors/Catsup0059/LunarRegolithParticleAnalysis.svg?style=flat-square
[contributors-url]: https://github.com/Catsup0059/LunarRegolithParticleAnalysis/graphs/contributors

[forks-shield]: https://img.shields.io/github/forks/Catsup0059/LunarRegolithParticleAnalysis.svg?style=flat-square
[forks-url]: https://github.com/Catsup0059/LunarRegolithParticleAnalysis/network/members

[stars-shield]: https://img.shields.io/github/stars/Catsup0059/LunarRegolithParticleAnalysis.svg?style=flat-square
[stars-url]: https://github.com/Catsup0059/LunarRegolithParticleAnalysis/stargazers

[issues-shield]: https://img.shields.io/github/issues/Catsup0059/LunarRegolithParticleAnalysis.svg?style=flat-square
[issues-url]: https://github.com/Catsup0059/LunarRegolithParticleAnalysis/issues

[license-shield]: https://img.shields.io/github/license/Catsup0059/LunarRegolithParticleAnalysis.svg?style=flat-square
[license-url]: https://github.com/Catsup0059/LunarRegolithParticleAnalysis/blob/HPC_hit/LICENSE.txt

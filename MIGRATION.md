# LUPA 从 MATLAB 到 Python 的迁移说明

LUPA Python 版实现 STL 预处理、形态与表面纹理指标计算、批量处理和结果显示。程序入口为仓库根目录的 `main.py`，实现位于 `lupa/`，运行依赖见 `requirements.txt`。

## 功能对应关系

| 原入口或调用位置 | Python 实现 | 迁移内容 |
| --- | --- | --- |
| `main.m` | `main.py`、`lupa/cli.py`、`lupa/pipeline.py` | 配置加载、处理阶段调度、多进程执行、进度及结果路径输出 |
| `read_ini.m`、`analysis.ini` | `lupa/config.py`、`analysis.ini` | INI 读取、指标开关、路径与算法参数；相对路径以配置文件所在目录为基准 |
| `utiliz_/import_stl.m` 及其中 `import_obj` | `lupa/pipeline.py` 的 `preprocess_particle`、`run_pipeline` | 按颗粒组织修复、简化、STL 和网格中间数据保存 |
| `repair_stl.m` | `lupa/mesh.py` 的 `repair_mesh` | 连通表面划分、各组件面积计算、保留最大面积组件、按配置居中 |
| 原 `readSTL`、`readSTL_central`、`stlreadASCII_central`、`SpharmMatUtilImportObjs` 调用链 | `lupa/mesh.py` 的 `Mesh`、`read_stl`、`clean_mesh`、`save_mesh`、`load_mesh` | Python STL 编解码、重合顶点与重复/零面积面清理、原点记录、NPZ 和旧 MAT 网格读取；不调用原工具箱代码 |
| `utiliz_/filter_stl.m`、`filter_stl.py`、`scripts/filter_stl_wrapper.py` | `lupa/mesh.py` 的 `filter_mesh` | 在当前 Python 进程中调用 PyMeshLab，保持二次误差边折叠和目标保留面数比例语义 |
| `utiliz_/particle_analysis.m` | `lupa/pipeline.py` 的 `analyze_particle`、`_export` | 依颗粒名称及简化标记配对，按开关计算13项结果，汇总为 CSV 与 JSON |
| `utiliz_/size_obj.m` | `lupa/metrics.py` 的 `size_metrics` | 三角面面积、有符号四面体体积求和、等效体积直径、比表面积、Wadell 球形度 |
| `utiliz_/calculate_pca.m` | `lupa/metrics.py` 的 `pca_metrics` | 点云中心化、SVD 主轴投影、主轴跨度排序及 EI/FI/AR 计算 |
| `utiliz_/cart2.m` | `lupa/metrics.py` 的 `cart2`、`shape_variance` | 保留方位角、仰角、半径和径向距离样本方差接口；批分析使用其中的径向方差，角度单位为弧度 |
| `utiliz_/calculate_roughness.m` | `lupa/metrics.py` 的 `roughness`、`point_triangle_distance` | 近邻顶点关联面筛选、点到三角形距离、Ra 和 Rz；保留可选有符号距离接口 |
| `utiliz_/calculate_fractal_dimension_dilation.m` | `lupa/fractal.py` 的 `fractal_dimension` | 表面体素化、半径选取、球形膨胀体积、对数线性拟合、分形维数及拟合优度 |
| `utiliz_/sph_display_repair.m`、`sph_display_filter.m` 及主流程中的 `ParticleDisplayObjs` | `lupa/pipeline.py` 的 `display_particle`、`lupa/render.py` | 修复/简化网格的实体、线框或组合绘制，PNG 导出及屏幕显示 |
| 新增桌面入口 | `lupa/gui.py` | 配置文件选择、路径和参数编辑、指标勾选、运行进度、结果表及图像查看 |

原 SPHARM-MAT 工具箱还包含球谐参数化、球谐系数展开与重建、形状配准、医学影像导入和统计分析等功能。这些功能没有在原 `main.m` 的颗粒分析调用链中执行，本版未将整个第三方工具箱翻译成 Python，也不把这些能力列为本版功能。

## 数值定义和坐标约定

`d_v`、`SSA`、Wadell 球形度、PCA 轴比、径向方差的定义沿用原颗粒分析程序。尺寸和体积指标的输入应为闭合、面片方向一致的三角网格；“修复”指提取最大面积连通表面，不表示已实现任意网格补洞或非流形重建。

Ra 是修复网格各顶点到简化网格候选三角面距离绝对值的均值。**Rz 定义为距离的样本标准差**，即 `sqrt(sum((d-mean(d))**2)/(n-1))`；单样本按 MATLAB `var` 的定义返回0。候选面来自 `k` 个最近顶点的关联面，默认 `k=10`。

Python 的 `faces` 使用从0开始的顶点索引，旧 MATLAB MAT 文件读取时将1基索引减1。`vertices + origin` 表示输入坐标系中的顶点；NPZ 同时保存 `vertices`、`faces`、`origin`。修复网格居中一次，简化网格继承相同的 `origin`，粗糙度计算使用共同坐标系。

分形计算延续原“体素中心到最近顶点距离不超过 `sqrt(3) * voxel_size`”的表面近似、物理半径取样与 `D = 3 - slope` 拟合定义。Python 用欧氏距离变换配合相同整数体素半径阈值计算球形膨胀结果，替代逐次构造球形结构元素；仍使用取整后的半径膨胀，并沿用原物理半径作拟合横坐标。该方法仍受顶点采样密度、体素大小和拟合尺度影响。

软件不从 STL 自动推断单位。长度指标沿用输入坐标单位，面积和体积相应取二次/三次方；分形配置与输出标签按毫米解释，应将输入坐标和配置统一为毫米后使用该模块。

## 输入输出与配置变化

- 输入新增对二进制 STL 的支持，ASCII STL 仍可读取；STL 输出为 ASCII 文本。STL 仅保存当前网格坐标，坐标原点记录在 NPZ 中。
- 中间网格使用 `.npz` 格式。`load_mesh` 通过 `scipy.io.loadmat` 读取含 `vertices`、`faces`、`origin` 的旧 MAT 文件；MATLAB v7.3 HDF5 格式不受支持。
- 仅分析或显示阶段会优先读取同名 NPZ，也支持配对的旧 MAT 网格。若旧 MAT 在分别居中后将 `origin` 均写成零，丢失的位移不能由读取器自动恢复，应从原 STL 重新执行预处理。
- 颗粒配对使用名称和 `PercentDescription`，不再依赖目录枚举顺序。该标记作为字符串保留前导零；旧 MATLAB 文件名若是 `_filter_1_obj.mat`，相应配置标记需填写 `1`，不能填写 `01`。
- `Percent` 表示简化后保留的目标面数比例，不是删除比例。新示例配置用 `0.5`、标记 `05`；指标和分形开关均由配置控制，不直接沿用原 `main.m` 中硬编码的布尔参数。
- 新版不使用 `PythonExe` 或另启 Python 包装脚本；启动本程序的 Python 环境应已安装 `requirements.txt` 中的依赖。
- 结果包含颗粒名及13项指标，输出 CSV、JSON。JSON 记录启用指标、配置与 Rz 定义；未启用指标仍用0占位，应结合 `enabled_metrics` 解读。
- 启用分形计算时，每个颗粒另保存膨胀半径、体积、拟合结果的 NPZ 数据和 PNG 拟合图。网格图像保存为 PNG。
- 原球谐显示参数 `Space=param`、`Mesh=icosa*`、`Degree`、`Overlay=adc_paramap` 没有成为本版处理参数。本版显示实际修复/简化后的网格，不生成球谐参数球或重建系数。

## 实现与依赖

`lupa/` 包含网格读写、指标计算、体素组织及批处理流程。PyMeshLab 提供网格简化，NumPy/SciPy 提供基础数值工具，Matplotlib 提供绘图功能；具体版本、作者和许可文件见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。


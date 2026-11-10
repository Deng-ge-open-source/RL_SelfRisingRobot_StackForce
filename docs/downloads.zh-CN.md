# 下载与版本

简体中文 · [English](downloads.en.md) · [首页](../README.md)

本发布提供 **结构件＋成品固件＋实物示例＋本地仿真运行包**。Studio 控制器源码不在发布范围内。实物例子采用网站适配的作者原版起立策略。

| 下载 | 用途 |
|---|---|
| [ESP32 成品固件](../SelfRising-ESP32-Firmware.zip) | 原版 ESP32 / 4 MB，包含四个烧录文件、地址、校验与许可说明 |
| [Sim2Real 示例工程](../SelfRising-ESP32.sim) | 在网站导入，校准后上传策略；A0→GPIO25、A1→GPIO26 |
| [MuJoCo 本地运行包](../SelfRising-MuJoCo.zip) | 在电脑上运行同一份策略，含模型、Python 运行器和 Windows/Linux 启动脚本 |
| [STL 打印包](../SelfRising-90S-STL.zip) | 四个分件与整机参考 STL |
| [STEP 图纸包](../SelfRising-90S-STEP.zip) | 四个可编辑实体与整机装配 STEP |
| [SHA-256 校验值](../SHA256SUMS) | 核对上述下载 |

## 先测试实物

1. 按[首页接线图](../README.md#step-4)完成装配。两只 MG90S 由独立 5 V 供电，与 ESP32、BNO055 共地。
2. 用网页安装器安装固件，再连接 USB，打开下载的 `.sim`。详细步骤见[运行教程](running.zh-CN.md)。
3. 保存自己的两轴零位、方向、行程和 BNO055 安装方向，上传策略，再点「运行」。

固件压缩包适合留存或用其他工具烧录。网页安装器提供板型识别与已有存储的保留流程，建议首次复现沿用网页操作。

## 在本地仿真

完整解压 `SelfRising-MuJoCo.zip`，保留 `module/`、`sim2sim/` 和 `manifest.json` 的相对位置。

- Windows：双击 `sim2sim/run_mujoco.cmd`。
- Linux：在包目录运行 `bash sim2sim/run_mujoco.sh`。

首次启动会建立独立 Python 环境并安装依赖，需要网络；后续复用该环境。本地仿真程序运行在电脑上，实物推理运行在 ESP32 上。

## 版本核对

固件 ID、板型、文件哈希及示例来源见 [release-manifest.json](../release-manifest.json)。固件和示例是分开的：烧录固件后，空板仍需完成校准和策略上传。每台机构的校准单独保存。

发布检查覆盖下载完整性、示例与本地包的策略一致性、本地原生 MuJoCo 执行及文档链接。此次打包没有重新刷板或做新的机械起立测试。SimReady 新训练策略的自动交接仍有兼容提示，见[训练教程第 5 步](training.zh-CN.md#5-进入-sim2sim)。

本地包已执行 15,000 个物理步、750 次策略推理，数值与输入输出检查通过。这不等同于四方向起立验收。本机离屏渲染遇到 8192 阴影缓冲初始化失败，交互窗口及不同显卡上的显示仍需审核。网页截图和本地离屏渲染是两种不同的显示路径。详见[本次发布验证记录](release-validation.json)。

许可分别列在 [LICENSE.md](../LICENSE.md)，包括结构件 GPL、固件二进制许可和第三方资源声明。

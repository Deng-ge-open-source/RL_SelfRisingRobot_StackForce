# SelfRising · Sim2Sim 本地运行包

本目录是仓库 [SelfRising-MuJoCo.zip](../../SelfRising-MuJoCo.zip) 的完整展开版本，包含网站导出的模型、策略、配置和本地启动脚本。直接使用压缩包时，完整解压后按同样方式运行。

- Windows：双击 `sim2sim/run_mujoco.cmd`。
- Linux：在本目录运行 `bash sim2sim/run_mujoco.sh`。
- 首次运行需要联网准备 Python 环境和依赖，后续复用环境。完整说明见 [包内启动文档](sim2sim/README.md)。

`module/`、`sim2sim/` 和 `manifest.json` 需要保持相对位置。内置策略与实物教程配套策略一致；它不是旁边 SimReady 参考动作工程新训练的九输入模型。已有验证范围见 [发布验证](../../docs/release-validation.json)。

## English

This is the full extracted version of [SelfRising-MuJoCo.zip](../../SelfRising-MuJoCo.zip), containing the website-exported model, policy, configuration and local launchers. On Windows, double-click `sim2sim/run_mujoco.cmd`. On Linux, run `bash sim2sim/run_mujoco.sh` from this folder. Internet access is needed for initial dependency setup. Keep the directory layout intact. See the [bundled instructions](sim2sim/README.md).

This package uses the supplied original-author policy, matching the hardware example. It does not use the newly trained nine-input reference policy. See the repository's validation and provenance records.

# SelfRising · SimReady 训练工程

[English](#english) · [返回教程](../README.md#step-7)

这是从 [SimReady 的 SelfRising 示例](https://sim.stackforce.cc/?example=23)“导出训练工程”页面下载的工程，模型、参考动作与训练配置直接放在本目录中。

## 打开和使用

1. 在 SimReady 里打开 `SelfRising-tutorial-trained.simready`，可恢复教程使用的工程和第 300 轮结果。
2. 在“训练”页查看参考动作、训练设置及历史模型；要重新训练时，连接支持 `referenceLearningV1` 的运行器，再点击“开始训练”。
3. `reference-learning.json` 是四方向参考动作；`config/effective-training.json` 记录导出设置，`src/` 中包含机器人 MJCF 和网格。
4. `result/` 保存这次教程训练的 ONNX、评估和运行约定。此模型为 **9 输入、2 输出**，与实物教程配套的作者策略不同；不要替换实物工程中的 ONNX。

## 导出模式说明

网页中选择的出口名称是 MJLab，但此 SelfRising 参考动作示例实际导出的 `training_engine` 是 **`native_mujoco_bc_v1`（原生 MuJoCo + PyTorch 模仿学习）**。原始包没有 MJLab PPO 任务注册或命令行启动脚本，不能用 `uv run train ...` 当作独立 MJLab PPO 工程启动。本目录保留网站导出的原样内容，不将它标为已验证的 MJLab PPO 训练包。

教程训练结果在四个规定仿真初态通过回放；实物部署和不同初态需要分别验证。这个文件夹没有运行新的训练。

## English

This is the original project freshly downloaded from SimReady's **Export Training Project** page with the MJLab export option. Its model, reference motions and configuration are directly available in this folder. The original export notes are retained in `EXPORT-NOTES.md`. Open `SelfRising-tutorial-trained.simready` in SimReady to restore the tutorial project and iteration-300 result.

The actual exported engine is **native MuJoCo + PyTorch behavior cloning (`native_mujoco_bc_v1`)**, not MJLab PPO. The original export has no standalone MJLab PPO task registration or CLI entry point. Use a SimReady Runner with `referenceLearningV1`. No new training was run to prepare this folder.

The result policy has **9 inputs and 2 outputs**. It is distinct from the original-author policy in the hardware tutorial and the local Sim2Sim package. Do not swap these ONNX files. Upstream model and policy provenance follows [the repository notices](../THIRD-PARTY-NOTICES.md).

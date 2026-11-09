# SelfRising · ESP32 示例工程

简体中文 · English below

[下载 SelfRising-ESP32.sim](../SelfRising-ESP32.sim)，在 [Sim2Real](https://sim2real.stackforce.cc/) 的导入页打开，或用网页右侧「打开工程」载入。工程采用当前网站适配的作者原版策略，与本发布的本地 MuJoCo 包使用同一份 ONNX。

| 项目 | 配置 |
|---|---|
| 下方舵机 / A0 | `servo1_joint` → GPIO25 |
| 上方舵机 / A1 | `servo2_joint` → GPIO26 |
| BNO055 | SDA→GPIO19，SCL→GPIO22；模块地址模板为 0x29 |
| 策略 | 50 Hz，10 输入 / 10 输出；2 路电机、8 路控制器状态 |
| 个人校准 | 不随模板提供；读取并保存自己的舵机中位、方向、行程与 IMU 安装方向 |

该工程不是 SimReady 本轮新训练的 9 输入参考策略。新训练路线的兼容状态见 [训练教程](../docs/training.zh-CN.md)。此处导入工程不会代替校准，也不表示已经给板卡上传或开始输出。

SHA-256 与下载来源见 [release-manifest.json](../release-manifest.json)。作者出处和模型许可范围见 [第三方说明](../THIRD-PARTY-NOTICES.md)。

## English

Open the linked `.sim` file in the Sim2Real import page or with **Open project**. It contains the website-adapted original-author policy, using exactly the same ONNX as this release's local MuJoCo package.

A0/lower servo maps to GPIO25; A1/upper servo maps to GPIO26. BNO055 uses SDA19/SCL22, with 0x29 in the template. The controller runs at 50 Hz with ten inputs and ten outputs: two motor channels and eight state channels. Personal neutral, direction, travel and IMU mounting calibration are not included.

This is the supplied author-policy example. See the training guide for the separately trained nine-input reference policy and its compatibility status. Importing the file does not upload it to hardware, calibrate the mechanism or start outputs. Hashes and provenance are recorded in the linked release manifest and third-party notices.

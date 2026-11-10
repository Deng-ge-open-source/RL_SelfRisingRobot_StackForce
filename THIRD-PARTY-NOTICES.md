# 第三方来源 · Third-party notices

## 机器人与策略 · Robot and policy

HomeMadeGarbage 的 [SelfRisingRobot / poco](https://github.com/homemadegarbage/SelfRisingRobot/tree/c344c2a4a1a51562247528d8aadcc0a527b6b103) 提供原始模型与神经网络权重。本站示例使用该版本的网络，通过适配保留作者的起立控制过程，并改用 BNO055 机体 Roll/Pitch 和 GPIO 舵机端点。网络没有在此实物示例中重新训练。

The original model and neural weights come from the pinned HomeMadeGarbage project. The supplied hardware example preserves that network and adapts its get-up controller to BNO055 body Roll/Pitch and GPIO servo endpoints. The supplied author-policy example is not a retrained policy.

- 原始网络头文件 SHA-256 / Original network header: `53832697be6668fe07bc80038ddde23af88b54d964e1d5affcb879104f998cf2`.
- 网站适配 ONNX SHA-256 / Adapted ONNX: `2b87ee3aee75e3198c782674af10fd34f23dfccc988591ca6ed8494d23cb4e66`.
- 10 路输入、10 路输出；两路用于舵机，八路用于控制器状态。策略周期 50 Hz / Ten inputs and outputs; two physical motor outputs and eight state channels, at 50 Hz.

发布时上游仓库未声明可据以重新许可这些资源的统一许可证。本发布保留作者署名和来源，不将作者模型、参数或策略宣称为本站原创，也不对其追加 GPL 或 MIT 授权。进一步利用时应核对上游权利人的授权范围。

At release time no repository-wide upstream licence was identified that authorises relicensing these resources. Attribution and provenance are retained. This release does not claim ownership of, or grant a new GPL/MIT licence over, the upstream model, weights or policy. Check upstream permissions for further use.

实物 `.sim` 包中的 `provenance/policy_network.h` 是原作者网络参数出处文件，不是 StackForce Studio 控制器固件源码。本站适配示例按下载时的字节保留；本地运行包的原有内容不变，新增许可说明。校验值见 [SHA256SUMS](SHA256SUMS)。

The `.sim` example's `provenance/policy_network.h` records the author's network parameters; it is not the StackForce Studio controller firmware source. The hardware example is retained byte-for-byte. Existing runtime contents are unchanged and licence notices were added. See [SHA256SUMS](SHA256SUMS).

## 固件组件 · Firmware components

原版 ESP32 目标基于 ESP-IDF 6.0 系列。Espressif 原创组件主要采用 Apache-2.0，其他组件包含 MIT/BSD 等声明。随固件提供对应通知及许可证文本，见 [firmware/esp32/third-party](firmware/esp32/third-party)。固件二进制下载不包含 ESP-IDF、cJSON 或 Studio 的源码树。

The original ESP32 target uses ESP-IDF 6.0. Espressif-authored components primarily use Apache-2.0; other components retain MIT/BSD and other notices. Licence texts accompany the firmware under the linked directory. The binary download does not contain the ESP-IDF, cJSON or Studio source trees.

参考 / References: [ESP-IDF v6.0.1 copyrights](https://github.com/espressif/esp-idf/blob/v6.0.1/docs/en/COPYRIGHT.rst), [cJSON](https://github.com/DaveGamble/cJSON).

## 本地仿真依赖 · Simulation dependencies

MuJoCo、NumPy、ONNX Runtime 和 Pillow 由运行包的依赖安装器另行安装，保留其许可证。示例的原作者模型与权重不包含在运行器脚本的 MIT 授权范围内。

MuJoCo, NumPy, ONNX Runtime and Pillow are installed separately by the runtime launchers and retain their own licences. The runtime scripts' MIT grant does not relicense the author's model or weights.

## 图片与结构件 · Images and hardware

LOLIN32 Lite 的板卡辨识参考来源为 [CircuitPython 板卡页](https://circuitpython.org/board/wemos_lolin32_lite/)。接线图为本项目整理；网站截图为实际 SelfRising 页面。用户修改的四个打印件采用 GPL-3.0-only；整机中的外购舵机参考几何保留独立来源。第三方商标与品牌属于各自权利人。

The board identification reference is the linked CircuitPython board page. Wiring diagrams were prepared for this project and website captures show the actual SelfRising example. The user's four modified printable designs use GPL-3.0-only; purchased servo reference geometry has separate provenance. Third-party trademarks belong to their respective owners.

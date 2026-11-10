# SelfRising motion policy / 不倒翁运动策略

[Download ONNX](selfrising-get-up.onnx) · [配套实机工程 / Hardware project](../SelfRising-ESP32.sim)

This is the supplied original-author get-up network adapted to the website deployment workflow. It has 10 inputs and 10 outputs: two motor outputs and eight controller-state outputs, evaluated at 50 Hz. Use the matching hardware project for the observation and action configuration. See the [upstream provenance and licence scope](../THIRD-PARTY-NOTICES.md).

这是网站部署流程配套的作者原版起立策略适配文件，输入、输出各 10 路，其中两路输出用于舵机，其余八路用于控制器状态，策略周期为 50 Hz。配套实机工程包含观测与动作配置。策略来源和许可范围见[第三方说明](../THIRD-PARTY-NOTICES.md)。

SHA-256: `2b87ee3aee75e3198c782674af10fd34f23dfccc988591ca6ed8494d23cb4e66`

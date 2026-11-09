# 分项许可 · Licence scope

本仓库包含开放结构件、运行脚本、成品固件和第三方示例资源。各部分分别许可；仓库没有统一套用 GPL。

This repository distributes hardware designs, local runtime scripts, binary firmware and third-party example resources under separate terms.

| 内容 / Material | 许可范围 / Terms |
|---|---|
| `hardware/stl/`、`hardware/step/` 中设计者修改的五个打印件 | `GPL-3.0-only`，见 [GPL 正文](hardware/stl/COPYING)。舵机参考几何保留各自来源 / The designer's five modified printable designs use GPL-3.0-only. Servo reference geometry retains its own provenance. |
| `firmware/esp32/` 的 StackForce 固件二进制 | [固件二进制使用许可](licenses/firmware-binary.txt)，不提供 Studio 控制器源码 / Binary-use permission; Studio controller source is not distributed. |
| `SelfRising-MuJoCo.zip` 中 StackForce 编写的 Python 运行器及启动脚本 | [MIT](licenses/runtime-MIT.txt)。通过依赖安装器另行取得的库遵循各自许可 / MIT for StackForce-authored runtime and launcher scripts; installed dependencies retain their licences. |
| 示例中的 HomeMadeGarbage 模型、网络参数与派生策略 | 保留作者来源，本站不重新声明为 GPL 或 MIT；见 [第三方说明](THIRD-PARTY-NOTICES.md) / Upstream rights are retained; no new GPL or MIT licence is asserted over these resources. |
| 本仓库编写的教程、接线图和实际网站截图 | 可复制、分享和署名转载，用于复现、教学及项目介绍；保留 StackForce 与原作者出处。第三方商标、照片和模型的权利保持不变 / Permission is granted to copy, share and reproduce these materials with attribution for reproduction, teaching and project documentation. Third-party rights remain unchanged. |

GPL 对打印件的许可不自动适用于分开分发的固件。固件中的第三方组件仍按各自许可提供，相关声明随固件下载包保留。

The GPL grant for the printable designs does not declare the separately distributed firmware to be GPL-licensed. Third-party firmware components retain their own licences and notices.

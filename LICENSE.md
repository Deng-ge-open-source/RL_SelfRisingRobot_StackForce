# 分项许可 · Licence scope

本仓库包含开放结构件、运行脚本、成品固件和第三方示例资源。各部分分别许可；仓库没有统一套用 GPL。

This repository distributes hardware designs, local runtime scripts, binary firmware and third-party example resources under separate terms.

<table align="center">
<thead>
<tr>
<th align="center">内容 / Material</th>
<th align="center">许可范围 / Terms</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center"><code>hardware/stl/</code>、<code>hardware/step/</code> 中设计者修改的四个打印件</td>
<td align="center"><code>GPL-3.0-only</code>，见 <a href="hardware/stl/COPYING">GPL 正文</a>。舵机参考几何保留各自来源 / The designer's four modified printable designs use GPL-3.0-only. Servo reference geometry retains its own provenance.</td>
</tr>
<tr>
<td align="center"><code>firmware/esp32/</code> 的 StackForce 固件二进制</td>
<td align="center"><a href="licenses/firmware-binary.txt">固件二进制使用许可</a> / Binary-use permission.</td>
</tr>
<tr>
<td align="center"><code>Sim-to-Sim/</code> 中 StackForce 编写的 Python 运行器及启动脚本</td>
<td align="center"><a href="licenses/runtime-MIT.txt">MIT</a>。通过依赖安装器另行取得的库遵循各自许可 / MIT for StackForce-authored runtime and launcher scripts; installed dependencies retain their licences.</td>
</tr>
<tr>
<td align="center">示例中的 HomeMadeGarbage 模型、网络参数与派生策略</td>
<td align="center">保留作者来源，本站不重新声明为 GPL 或 MIT；见 <a href="THIRD-PARTY-NOTICES.md">第三方说明</a> / Upstream rights are retained; no new GPL or MIT licence is asserted over these resources.</td>
</tr>
<tr>
<td align="center">本仓库编写的教程、接线图和实际网站截图</td>
<td align="center">可复制、分享和署名转载，用于复现、教学及项目介绍；保留 StackForce 与原作者出处。第三方商标、照片和模型的权利保持不变 / Permission is granted to copy, share and reproduce these materials with attribution for reproduction, teaching and project documentation. Third-party rights remain unchanged.</td>
</tr>
</tbody>
</table>

GPL 对打印件的许可不自动适用于分开分发的固件。固件中的第三方组件仍按各自许可提供，相关声明随固件下载包保留。

The GPL grant for the printable designs does not declare the separately distributed firmware to be GPL-licensed. Third-party firmware components retain their own licences and notices.

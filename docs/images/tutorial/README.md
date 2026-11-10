# SelfRising 教程截图 · Screenshot provenance

截图于 2026-11-09 从实际网站采集，中文、英文界面分别拍摄。全部为 **1920 × 1080、16:9 PNG**。

Captures show the actual websites on 2026-11-09. Chinese and English interfaces were captured separately. Every image is a **1920 × 1080, 16:9 PNG**.

<table align="center">
<thead>
<tr>
<th align="center">文件 · File</th>
<th align="center">页面状态 · Page state</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center"><code>01-selfrising.png</code></td>
<td align="center">SimReady <code>example=23</code>，已载入 <code>robo1</code> · SelfRising imported</td>
</tr>
<tr>
<td align="center"><code>02-mapping.png</code></td>
<td align="center">模板原有 2 路动作、9 路观测 · Template's two actions and nine observations</td>
</tr>
<tr>
<td align="center"><code>03-connect-runner.png</code></td>
<td align="center">未配对时的运行器下载入口 · Runner download before pairing</td>
</tr>
<tr>
<td align="center"><code>03-training-ready.png</code></td>
<td align="center">已配对，CPU / 1 环境 / 300 轮 / 保存间隔 100 / 种子 42 · Paired, configured training page</td>
</tr>
<tr>
<td align="center"><code>03-ppo-mode.png</code></td>
<td align="center">实际 BC → PPO 配置入口；本轮未执行 PPO · Actual BC → PPO setting; PPO not executed in this test</td>
</tr>
<tr>
<td align="center"><code>05-training-complete.png</code></td>
<td align="center">本次 BC 300 轮训练完成 · This run's completed BC training</td>
</tr>
<tr>
<td align="center"><code>06-replay.png</code></td>
<td align="center">同一训练结果的实际在线回放 · Live replay of that trained result</td>
</tr>
<tr>
<td align="center"><code>07-handoff.png</code></td>
<td align="center">选择本次训练模型交接或下载 · This run's model handoff and download controls</td>
</tr>
<tr>
<td align="center"><code>07-handoff-warning.png</code></td>
<td align="center">实际出现的运行能力不兼容提示 · Observed runtime-capability incompatibility</td>
</tr>
<tr>
<td align="center"><code>08-sim2sim-original.png</code></td>
<td align="center">网站自带作者原版示例的 MuJoCo 页面 · MuJoCo page for the supplied original-author example</td>
</tr>
<tr>
<td align="center"><code>09-connect-esp32.png</code></td>
<td align="center">实物部署，板卡未连接 · Hardware deployment before controller connection</td>
</tr>
<tr>
<td align="center"><code>10-install-firmware.png</code></td>
<td align="center">选择 ESP32 · 4MB，尚未烧录 · ESP32 · 4MB selected before flashing</td>
</tr>
</tbody>
</table>

每个文件在 `zh-CN/` 与 `en/` 下各一份。采集使用经用户同意的独立后台浏览器，直接保存网页视口；不含应用边框或 ChatGPT 浮动输入框，未重绘界面、伪造板卡或替换图中机器人。网站自身尚未翻译的少量标签保留原样。

Each filename has a capture under both `zh-CN/` and `en/`. An independent headless browser, approved by the user, saved the webpage viewport directly. Images exclude application chrome and the ChatGPT composer. UI, devices and robots were not fabricated or repainted. A few untranslated labels from the website remain as displayed.

训练、回放与导出的策略哈希一致。原版作者示例单独标明。实物截图本轮没有烧录、使能或驱动舵机。参数、软件版本和验证范围见[实测记录](../../training-evidence.json)。

The trained, replayed and exported policy hashes match. The supplied original-author example is identified separately. No controller was flashed and no motors were enabled or driven for these hardware screenshots. See the [test record](../../training-evidence.json) for parameters, versions and scope.


## English-label revision · 英文标注修订

English tutorial figures now use `.svg` versions where the website had untranslated labels. Only the example name, AI API label, motion-fit label and package-download message were translated. Robot poses, numerical settings, recorded results and failure messages are unchanged. The original unedited PNG captures are retained in the `v0.1.0-rc.1` tag. The English calibration figure is a labelled vector illustration of the controls with example values, not a claim of a new live hardware connection. The English import figure crops out an unrelated utility dock. All tutorial canvases remain 16:9.

英文教程对网页残留中文的图使用了 SVG 英文标注版，仅翻译文字，模型姿态、参数、测试结果与错误状态不变。未经修改的原始 PNG 仍保存在 `v0.1.0-rc.1`。英文校准图为控件与示例值的矢量说明图，不代表新连接的实机状态；英文导入图裁去无关的悬浮工具。教程画布继续使用 16:9。

## 2026-11-10 animated replay

`zh-CN/06-replay.gif` and `en/06-replay.gif` replace the static replay image in the tutorials. Both are 16:9 recordings of the same completed iteration-300 tutorial policy, played in the actual SimReady interface. The original still images remain for provenance. See [capture metadata](replay-capture.json). No new training or hardware operation was performed.

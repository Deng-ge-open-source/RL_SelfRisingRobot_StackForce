# SelfRising 教程截图 · Screenshot provenance

截图于 2026-11-09 从实际网站采集，中文、英文界面分别拍摄。全部为 **1920 × 1080、16:9 PNG**。

Captures show the actual websites on 2026-11-09. Chinese and English interfaces were captured separately. Every image is a **1920 × 1080, 16:9 PNG**.

| 文件 · File | 页面状态 · Page state |
|---|---|
| `01-selfrising.png` | SimReady `example=23`，已载入 `robo1` · SelfRising imported |
| `02-mapping.png` | 模板原有 2 路动作、9 路观测 · Template's two actions and nine observations |
| `03-connect-runner.png` | 未配对时的运行器下载入口 · Runner download before pairing |
| `03-training-ready.png` | 已配对，CPU / 1 环境 / 300 轮 / 保存间隔 100 / 种子 42 · Paired, configured training page |
| `03-ppo-mode.png` | 实际 BC → PPO 配置入口；本轮未执行 PPO · Actual BC → PPO setting; PPO not executed in this test |
| `05-training-complete.png` | 本次 BC 300 轮训练完成 · This run's completed BC training |
| `06-replay.png` | 同一训练结果的实际在线回放 · Live replay of that trained result |
| `07-handoff.png` | 选择本次训练模型交接或下载 · This run's model handoff and download controls |
| `07-handoff-warning.png` | 实际出现的运行能力不兼容提示 · Observed runtime-capability incompatibility |
| `08-sim2sim-original.png` | 网站自带作者原版示例的 MuJoCo 页面 · MuJoCo page for the supplied original-author example |
| `09-connect-esp32.png` | 实物部署，板卡未连接 · Hardware deployment before controller connection |
| `10-install-firmware.png` | 选择 ESP32 · 4MB，尚未烧录 · ESP32 · 4MB selected before flashing |

每个文件在 `zh-CN/` 与 `en/` 下各一份。采集使用经用户同意的独立后台浏览器，直接保存网页视口；不含应用边框或 ChatGPT 浮动输入框，未重绘界面、伪造板卡或替换图中机器人。网站自身尚未翻译的少量标签保留原样。

Each filename has a capture under both `zh-CN/` and `en/`. An independent headless browser, approved by the user, saved the webpage viewport directly. Images exclude application chrome and the ChatGPT composer. UI, devices and robots were not fabricated or repainted. A few untranslated labels from the website remain as displayed.

训练、回放与导出的策略哈希一致。原版作者示例单独标明。实物截图本轮没有烧录、使能或驱动舵机。参数、软件版本和验证范围见[实测记录](../../training-evidence.json)。

The trained, replayed and exported policy hashes match. The supplied original-author example is identified separately. No controller was flashed and no motors were enabled or driven for these hardware screenshots. See the [test record](../../training-evidence.json) for parameters, versions and scope.

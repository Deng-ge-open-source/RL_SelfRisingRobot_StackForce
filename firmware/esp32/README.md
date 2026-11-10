# ESP32 成品固件 · Binary firmware

简体中文 · English below

适用本项目的 **LOLIN32 Lite / 原版 ESP32 / 4 MiB Flash / BNO055 / GPIO25、26**。ESP32-S3 使用不同固件。本目录提供可烧录的固件文件。

## 推荐安装方式

1. 打开 [SelfRising 实物示例](https://sim2real.stackforce.cc/?example=selfrising-2axis&autoplay=0&step=sim2real&connection=usb&panel=devices)。
2. 在「设备与映射」点「安装固件」，保持自动识别或选择「ESP32 · 4MB」。选择 USB 串口，等待写入与校验。
3. 点「USB 连接」。打开本发布的 `SelfRising-ESP32.sim`，核对 A0→GPIO25、A1→GPIO26，完成舵机及 BNO055 校准，再点「上传策略」。
4. 上传完成后，在「遥控操作」点「运行」。空板的首次安装还需要上传策略；本固件附件不包含现场设备的 NVS、Wi-Fi 密码或个人校准。已有 Studio 设备使用网页安装器识别并处理存储保留。

## 文件与写入地址

<table align="center">
<thead>
<tr>
<th align="center">地址</th>
<th align="center">文件</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center"><code>0x1000</code></td>
<td align="center"><code>1000-bootloader.bin</code></td>
</tr>
<tr>
<td align="center"><code>0x8000</code></td>
<td align="center"><code>8000-partition-table.bin</code></td>
</tr>
<tr>
<td align="center"><code>0xF000</code></td>
<td align="center"><code>f000-ota_data_initial.bin</code></td>
</tr>
<tr>
<td align="center"><code>0x20000</code></td>
<td align="center"><code>20000-stackforce_robot_controller.bin</code></td>
</tr>
</tbody>
</table>

Flash：DIO / 40 MHz / 4 MB。`manifest.json` 提供板型、文件大小与 SHA-256；`SHA256SUMS` 可校验此下载。不要把任一分区文件当作从地址 0 写入的整片 Flash 镜像。

需要使用其他烧录工具时，按表填写地址和文件。该地址表不替代旧设备的分区迁移；已有策略和校准的设备优先用网页安装器。

## 策略与自启

固件负责 BNO055、GPIO 舵机、参数保存、策略推理和 USB 通信；具体模型及映射由 `.sim` 工程提供。保存舵机与 IMU 校准后，再按网页提供的设置保存上电自启选择，并实际断电重上电验证。固件版本与模型是否已安装以板卡回报为准。

## 许可

见本目录 `BINARY-LICENSE.txt` 和 `third-party/`。打印件的 GPL 不自动应用到成品固件。随包许可证是通知文本，不是控制器源代码。

## English

Target: **LOLIN32 Lite, original ESP32, 4 MiB Flash, BNO055 and GPIO25/26**. ESP32-S3 uses a different image. This directory provides flashable firmware binaries.

Use the linked SelfRising hardware example in desktop Chrome/Edge. Open **Devices & mapping → Install firmware**, let the installer detect the board or select **ESP32 · 4MB**, choose the USB serial port and wait for verification. Connect USB afterward, open this release's `.sim` example, check A0→GPIO25 and A1→GPIO26, calibrate both servos and the IMU, then upload the policy and use **Run**.

The table gives the four flash addresses. Flash mode is DIO, frequency 40 MHz, capacity 4 MB. Each file is a partition image, not a complete flash image for address zero. Prefer the website installer for devices with existing Studio calibration or policies, so its storage detection/preservation flow is used.

This firmware download contains no personal NVS archive, Wi-Fi credentials or device calibration. A fresh board still needs its policy uploaded. Configure and save autostart using the installed firmware's controls, then verify it by a real power cycle. See `manifest.json`, `SHA256SUMS`, `BINARY-LICENSE.txt` and the accompanying third-party notices.

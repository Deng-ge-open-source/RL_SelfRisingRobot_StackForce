# StackForce SelfRising

[简体中文](README.md) · English

Print five parts, connect an ESP32, an orientation sensor and two servos, then deploy a get-up policy to the robot on your workbench.

<p align="center">
  <a href="https://sim2real.stackforce.cc/example-media/selfrising/red-base-preview-10s.mp4"><img src="docs/images/selfrising-get-up.gif" width="360" alt="The red-base, white-link SelfRising robot getting back up after a fall"></a>
</p>

<p align="center">
  <a href="#1-identify-the-board-and-gather-the-parts">Start the build</a> ·
  <a href="SelfRising-90S-STL.zip">Download the print pack</a> ·
  <a href="https://sim2sim.stackforce.cc/?example=selfrising-2axis&amp;autoplay=0">Try the simulation</a> ·
  <a href="https://sim2real.stackforce.cc/example-media/selfrising/red-base-preview-10s.mp4">Watch the full demo clip</a>
</p>

## 1. Identify the board and gather the parts

The hardware example uses a **LOLIN32 Lite with the original ESP32** and a CH340 USB serial interface. Hold the USB port at the bottom and locate `19`, `22`, `25`, `26`, `3V` and `G` on the board. Some versions label the power and ground pins `3V3` and `GND`.

See the wiring diagram in step 3. Match the printed labels on your own board before wiring. [Full board photograph](https://circuitpython.org/assets/images/boards/large/wemos_lolin32_lite.jpg) · [CircuitPython board page](https://circuitpython.org/board/wemos_lolin32_lite/) · [Board schematic](https://done.land/assets/files/lolin32_lite.pdf)

| Gather | Purpose |
|---|---|
| One LOLIN32 Lite and a USB data cable | Install firmware, connect to the website and run the policy |
| One BNO055 module with a 3.3 V compatible input | Read the body orientation |
| Two MG90S servos with matching horns and fasteners | Lower joint A0 and upper joint A1 |
| A **separate regulated 5 V supply** and wiring | Power both MG90S servos and share ground with the ESP32 |
| Five printed parts | Base, bottom cover, middle link, upper link and spacer ring |

To save time sourcing parts, buy a kit and follow the same assembly and deployment steps. The listing shows what is included. [View the kit on Taobao](https://e.tb.cn/h.jSReBRMxBI9FNul?tk=dqhs6cdMf8N)

## 2. Print and test the fit

1. Download the print pack and import the five numbered parts at **100% scale in millimetres**. Print the base and bottom cover in red and the links and spacer ring in white. [Download the STL pack](SelfRising-90S-STL.zip) · [Parts and dimensions](hardware/stl/README.md)
2. Check the fit of the base, both links and the spacer ring against the assembled robot in the lower-right panel. Position the servo horns loosely and secure them after aligning neutral in step 5. [Assembly STL](hardware/stl/SelfRising-90S-assembled.stl) · [Three-view assembly preview](docs/images/selfrising-assembled.png)

![Five red and white printed parts with the assembled robot in the lower-right panel](docs/images/print-parts.png)

## 3. Wire the robot

Disconnect power before wiring. Connect the computer to the ESP32 with the USB data cable. Connect both servo power leads to a separate regulated 5 V supply. Join the ESP32, BNO055, both servos and the negative terminal of the 5 V supply at common ground. Use the input on the BNO055 module rated for 3.3 V.

Mount the BNO055 on the fixed red base so it moves with the base. The diagram marks the mounting area. Match the labels on your module when wiring it.

<p align="center"><a href="docs/images/esp32-lolin32-lite.svg"><img src="docs/images/esp32-lolin32-lite.svg" width="820" alt="Complete wiring for LOLIN32 Lite, BNO055 and two MG90S servos"></a></p>

| From | To |
|---|---|
| ESP32 `GPIO19` | BNO055 `SDA` |
| ESP32 `GPIO22` | BNO055 `SCL` |
| ESP32 `3V3` | BNO055 3.3 V compatible power input |
| ESP32 `GPIO25` | Lower servo A0 signal |
| ESP32 `GPIO26` | Upper servo A1 signal |
| External regulated `+5 V` | Power input on both servos |
| Common `GND` | ESP32, BNO055, both servos and the supply’s negative terminal |

These pins match the ESP32 hardware template on the site. [Original ESP32 wiring reference](https://github.com/Deng-ge-open-source/Stack_Force_Sim2sim/blob/05eee9528c15bb03257c3b7f3654a401d8bd1ffb/apps/mujoco-online/hardware/esp32-robot-controller/original/README.md)

## 4. Open the site and connect the board

1. Open Sim2Real in desktop Chrome or Edge. Load **StackForce SelfRising · ESP32** from the example picker. [Open Sim2Real](https://sim2real.stackforce.cc/)
2. Connect the board with a USB data cable. On a fresh board, open **Install firmware** in **Devices & Mapping**, select **Choose board and install**, then select the board’s CH340 port. Wait for the site to confirm that it wrote and verified the firmware.
3. In **Devices & Mapping**, select **Connect USB** and choose the board’s port. Continue once the BNO055 readings and both GPIO servo channels appear. [Browser serial permissions](https://developer.chrome.com/docs/capabilities/serial)

## 5. Calibrate both axes

1. In **Devices & Mapping**, check **A0 → GPIO25** and **A1 → GPIO26**. Set the robot upright and check the displayed orientation against the BNO055 mounting direction.
2. Calibrate one servo at a time. Centre it, align the link to the model’s mechanical zero, then secure the horn. Jog each axis through a small movement to check its direction and travel. Save the calibration.
3. After checking neutral, direction and travel for both axes, select **Upload policy** and wait for confirmation.

## 6. Try one recovery

Set the robot on a stable, level surface with space for both links to move. Select **Run** in **Remote Control** and check the controller’s status. Try stopping and restarting once. Then begin from one controlled fall and observe the robot get up and return to neutral. You can also stop it from **Devices & Mapping**.

| If you see this | Check this first |
|---|---|
| No serial port appears | Use a USB data cable and select the correct CH340 port in the browser |
| No BNO055 readings | Verify SDA and SCL, power and common ground |
| A servo moves backwards or binds | Select Stop, then check that axis’s direction, mechanical zero and travel |
| The page asks you to upload a policy | Go back to Devices & Mapping, upload the current project’s policy and wait for confirmation |

You can practise the fall and recovery in simulation first. To train your own policy, start with the SimReady reference project and verify the export in simulation. [Try the simulation](https://sim2sim.stackforce.cc/?example=selfrising-2axis&autoplay=0) · [Train from scratch](https://sim.stackforce.cc/?example=23)

## Credits and licence

The StackForce SelfRising hardware designer modified this 90S print set. The five printable designs and their matching editable Creo files are licensed under GNU GPL v3.0 (`GPL-3.0-only`). [Print files and provenance](hardware/stl/README.md) · [GPL text](hardware/stl/COPYING)

The recovery policy comes from HomeMadeGarbage’s two-axis robot *poco*. StackForce integrates it into the general Sim2Sim and Sim2Real workflows and provides a hardware profile for the LOLIN32 Lite, BNO055 and GPIO servos. [Original project](https://github.com/homemadegarbage/SelfRisingRobot/tree/c344c2a4a1a51562247528d8aadcc0a527b6b103)

# Downloads and versions

[简体中文](downloads.zh-CN.md) · English · [Home](../README.en.md)

This release supplies **hardware designs, binary firmware, a hardware example and a local simulation runtime**. Studio controller source is not distributed. The hardware example uses the website-adapted original-author recovery policy.

<table align="center">
<thead>
<tr>
<th align="center">Download</th>
<th align="center">Purpose</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center"><a href="../SelfRising-ESP32-Firmware.zip">ESP32 binary firmware</a></td>
<td align="center">Original ESP32 / 4 MB; four flash images, addresses, checksums and licence notices</td>
</tr>
<tr>
<td align="center"><a href="../SelfRising-ESP32.sim">Sim2Real example</a></td>
<td align="center">Import into the website, calibrate and upload; A0→GPIO25, A1→GPIO26</td>
</tr>
<tr>
<td align="center"><a href="../SelfRising-MuJoCo.zip">Local MuJoCo runtime</a></td>
<td align="center">Run the same policy on a computer; model, Python runner and Windows/Linux launchers included</td>
</tr>
<tr>
<td align="center"><a href="../SelfRising-90S-STL.zip">STL print pack</a></td>
<td align="center">Four individual parts and assembled reference STL</td>
</tr>
<tr>
<td align="center"><a href="../SelfRising-90S-STEP.zip">STEP CAD pack</a></td>
<td align="center">Four solid parts and complete assembly</td>
</tr>
<tr>
<td align="center"><a href="../SHA256SUMS">SHA-256 checksums</a></td>
<td align="center">Verify the downloads</td>
</tr>
</tbody>
</table>

## Test the hardware

1. Assemble and wire the robot using the [homepage diagram](../README.en.md#step-4). Power both MG90S servos from a separate 5 V supply and join all grounds.
2. Install firmware with the website installer, connect USB and open the downloaded `.sim`. Follow the [running guide](running.en.md).
3. Save your own servo neutral, direction, travel and IMU mounting calibration, upload the policy, then select **Run**.

Keep the firmware archive for manual flashing or recovery. The website installer detects the board and handles preservation of recognised existing storage; it is the recommended reproduction path.

## Run local simulation

Extract the complete `SelfRising-MuJoCo.zip` archive, preserving the relative locations of `module/`, `sim2sim/` and `manifest.json`.

- Windows: double-click `sim2sim/run_mujoco.cmd`.
- Linux: run `bash sim2sim/run_mujoco.sh` from the extracted package.

The first launch creates an isolated Python environment and downloads dependencies. Later launches reuse it. Local simulation runs on the computer; hardware inference runs on the ESP32.

## Check the version

See [release-manifest.json](../release-manifest.json) for the firmware identity, board target, file hashes and source URLs. Firmware and the example are separate: a fresh board still needs calibration and policy upload. Calibration belongs to each physical mechanism.

Release checks cover artifact integrity, policy parity between the example and runtime, native local MuJoCo execution and documentation links. No new physical flashing or mechanical recovery test was performed while preparing this release. Automatic handoff of the newly trained SimReady policy still reports a compatibility issue; see [training step 5](training.en.md#5-open-sim2sim).

The local package completed 15,000 physics steps and 750 policy inferences with finite state and valid I/O. This is not four-direction recovery acceptance. Offscreen rendering on this machine failed to initialise the model's 8192 shadow buffer; the interactive viewer and display on other GPUs remain review items. Website captures and native offscreen rendering use different display paths. See the [release verification record](release-validation.json).

See [LICENSE.md](../LICENSE.md) for the scoped hardware, firmware, runtime and third-party terms.

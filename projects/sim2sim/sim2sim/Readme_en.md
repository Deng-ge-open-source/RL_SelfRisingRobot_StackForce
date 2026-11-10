# StackForce one-click MuJoCo guide

## What it does

MuJoCo does not need to be installed beforehand. On the first launch, the script
detects Python, creates the isolated `sim2sim/.venv` environment, installs
MuJoCo, ONNX Runtime, and the remaining requirements, verifies the installation,
and starts the exported project. Later launches reuse the environment and do not
reinstall unchanged dependencies.

The first setup needs internet access. Extract the complete package and keep the
`sim2sim`, `module`, policy, and model files in their original relative locations.

## Remote control

Runtime remote control is disabled for this project; the launcher keeps the command defaults declared by the profile.

## Windows

1. Extract the complete `.sfdeploy.zip` package.
2. Double-click `sim2sim/run_mujoco.cmd`.
3. Wait for setup to finish; the MuJoCo window opens automatically.

When Python 3.10+ is missing, the launcher uses Windows `winget` to install
Python 3.12 when available. Windows may show an installation confirmation.

Set up without starting MuJoCo:

```powershell
powershell -ExecutionPolicy Bypass -File sim2sim/run_mujoco.ps1 -SetupOnly
```

Force a dependency reinstall:

```powershell
powershell -ExecutionPolicy Bypass -File sim2sim/run_mujoco.ps1 -Reinstall
```

## Ubuntu

Run this from the extracted package directory:

```bash
bash sim2sim/run_mujoco.sh
```

If Python, `venv`, or MuJoCo viewer libraries are missing, the launcher installs
them through `apt`. It may ask for the user's `sudo` password.

Set up without starting MuJoCo:

```bash
STACKFORCE_MUJOCO_SETUP_ONLY=1 bash sim2sim/run_mujoco.sh
```

Force a dependency reinstall:

```bash
STACKFORCE_MUJOCO_REINSTALL=1 bash sim2sim/run_mujoco.sh
```

## Troubleshooting

- First setup fails: verify internet access to the Python package index and rerun the launcher.
- Windows has neither Python nor winget: install Python 3.10+ from
  https://www.python.org/downloads/ and launch the script again.
- Ubuntu cannot open a viewer: use a desktop session with a valid `DISPLAY`.
- The environment is damaged: use the force-reinstall command above.
- To select an existing Python, set `STACKFORCE_MUJOCO_PYTHON` to its executable path.

The launcher validates the model, native MuJoCo physics, ONNX session, and the
declared policy input/output dimensions.

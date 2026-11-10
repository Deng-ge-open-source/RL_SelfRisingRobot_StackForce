# Local MuJoCo validation

No separate MuJoCo installation is required. The launchers detect a compatible
Python, create `sim2sim/.venv`, install MuJoCo and the package dependencies
when needed, validate the installation, and then start the exported project.

1. Extract the complete deployment package and keep its directory structure.
2. On Windows, double-click `sim2sim/run_mujoco.cmd`. If Python 3.10+ is
   missing, the launcher attempts to install Python 3.12 with `winget`.
3. On Ubuntu, run `bash sim2sim/run_mujoco.sh`. If required, the launcher uses
   `apt`/`sudo` to install Python, `venv`, and MuJoCo viewer system libraries.
4. Keep internet access enabled for the first run. Later runs reuse the package's
   isolated `.venv` and start without reinstalling unchanged dependencies.

## Keyboard remote control

Runtime remote control is disabled for this project; the launcher keeps the command defaults declared by the profile.

Advanced options:

- Windows environment setup only: `powershell -ExecutionPolicy Bypass -File sim2sim/run_mujoco.ps1 -SetupOnly`
- Windows force reinstall: `powershell -ExecutionPolicy Bypass -File sim2sim/run_mujoco.ps1 -Reinstall`
- Ubuntu environment setup only: `STACKFORCE_MUJOCO_SETUP_ONLY=1 bash sim2sim/run_mujoco.sh`
- Ubuntu force reinstall: `STACKFORCE_MUJOCO_REINSTALL=1 bash sim2sim/run_mujoco.sh`

The launcher loads the exported MJCF in native MuJoCo, validates the ONNX session and declared dimensions, advances native physics, opens the MuJoCo viewer, and runs the profile's closed-loop policy and keyboard command configuration.

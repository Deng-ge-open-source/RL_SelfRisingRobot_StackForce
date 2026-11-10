# StackForce MuJoCo 一键运行说明

## 功能

无需提前安装 MuJoCo。首次启动时，脚本会自动检测 Python，创建包内独立环境
`sim2sim/.venv`，安装 MuJoCo、ONNX Runtime 等依赖，检查安装结果，然后启动工程。
以后再次启动会直接复用该环境，不会重复安装未变化的依赖。

首次安装需要网络连接。请完整解压导出包，不要单独移动 `sim2sim`、`module` 或模型文件。

## 遥控操作

此工程没有启用运行时遥控；启动器会保留 profile 中的默认 command。

## Windows

1. 打开本仓库完整的 `Sim-to-Sim/` 文件夹。
2. 双击 `sim2sim/run_mujoco.cmd`。
3. 等待自动配置完成，MuJoCo 窗口会随后打开。

如果电脑没有 Python 3.10+，脚本会优先使用 Windows 的 `winget` 自动安装
Python 3.12。系统可能弹出安装确认窗口。

仅配置环境，不启动 MuJoCo：

```powershell
powershell -ExecutionPolicy Bypass -File sim2sim/run_mujoco.ps1 -SetupOnly
```

强制重新安装依赖：

```powershell
powershell -ExecutionPolicy Bypass -File sim2sim/run_mujoco.ps1 -Reinstall
```

## Ubuntu

在解压目录中运行：

```bash
bash sim2sim/run_mujoco.sh
```

如果缺少 Python、`venv` 或 MuJoCo 查看器依赖，脚本会通过 `apt` 安装，
期间可能要求输入 `sudo` 密码。

仅配置环境：

```bash
STACKFORCE_MUJOCO_SETUP_ONLY=1 bash sim2sim/run_mujoco.sh
```

强制重新安装依赖：

```bash
STACKFORCE_MUJOCO_REINSTALL=1 bash sim2sim/run_mujoco.sh
```

## 常见问题

- 首次安装失败：确认网络可以访问 Python 软件源，然后重新运行脚本。
- Windows 找不到 Python 且没有 winget：先从 https://www.python.org/downloads/ 安装
  Python 3.10+，再双击启动脚本。
- Ubuntu 无法打开图形窗口：确认当前会话有桌面显示环境和有效的 `DISPLAY`。
- 依赖损坏：使用上面的“强制重新安装”命令。
- 指定已有 Python：设置环境变量 `STACKFORCE_MUJOCO_PYTHON` 为 Python 可执行文件路径。

启动器会验证模型、原生 MuJoCo 物理、ONNX 会话和声明的输入输出维度。

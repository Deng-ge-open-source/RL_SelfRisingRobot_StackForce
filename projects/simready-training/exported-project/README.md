Reference learning v1

Native MuJoCo physics + PyTorch behavior cloning; not MJLab PPO.
The model, demonstration data, column mapping, initial weights and optimizer settings are self-contained.
Use the existing SimReady Start Training button with a Runner advertising referenceLearningV1.
Target controller: target = clip(target + clamp(action,-1,1)*delta, lower, upper).
Observations use radians and the last sent target. Runtime contract and evaluation are exported separately.

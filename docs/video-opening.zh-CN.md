# 强化学习不倒翁视频开场文案

记录日期：2026-11-12。以下保留确认的口播原文；训练方法的适用范围见下方核对说明。

## 口播原文

这是一个电子不倒翁。把它推倒，它就会用身上的两只小舵机，重新把自己撑起来。

而支撑它完成这个动作的，正是现在先进的人形机器人也在使用的那类控制方法——模仿学习和强化学习。

而这就是我今天要开源给大家的最小强化学习机器人项目。一百元以内，你就能用它体验机器人开发里的核心方法：模仿学习、强化学习，还有从仿真到实物部署的整个流程。

今天，我就将用最通俗的语言，手把手带大家把这个机器人做出来，再把从训练到实物部署的这套原理，一步一步拆开讲清楚。让你用百元级的成本，亲手走一遍机器人从设计、实验到部署的完整流程，入门前沿机器人的控制和部署方法。

## 训练方法核对

“用这个项目体验模仿学习和强化学习”有依据；“当前展示的起立策略已经经过模仿学习加强化学习训练”尚无充分依据。两种说法需要区分。

- **模仿学习（BC）**：从参考动作生成观测和动作示范，让网络拟合示范。原作者的[预训练脚本](https://github.com/homemadegarbage/SelfRisingRobot/blob/c344c2a4a1a51562247528d8aadcc0a527b6b103/RL/pretrain_robo1_from_scripted.py)创建 Stable-Baselines3 的 PPO 策略对象，但实际执行的是动作均方误差优化，没有调用 PPO 的 `learn()`。使用 PPO 网络或将文件命名为 PPO，不等于完成了强化学习训练。
- **强化学习（PPO）**：在环境中交互、依据奖励优化策略。原作者另有[强化学习脚本](https://github.com/homemadegarbage/SelfRisingRobot/blob/c344c2a4a1a51562247528d8aadcc0a527b6b103/RL/train_robo1.py)，明确调用 `model.learn()`；[训练说明](https://github.com/homemadegarbage/SelfRisingRobot/blob/c344c2a4a1a51562247528d8aadcc0a527b6b103/RL/README.md)提供先预训练、再继续 PPO 的操作流程。
- **上游公开模型**：只读检查固定版本的 [`robo1_getup_ppo.zip`](https://github.com/homemadegarbage/SelfRisingRobot/blob/c344c2a4a1a51562247528d8aadcc0a527b6b103/RL/robo1_getup_ppo.zip) 内的 JSON 元数据，`num_timesteps`、`_total_timesteps`、`_n_updates` 均为 `0`。结合上述预训练脚本，现有公开材料不能证明这份权重完成过后续 PPO 更新。此检查未执行模型文件或训练代码。
- **本仓库网页训练记录**：[训练实测记录](training-evidence.json)为 300 轮 BC；[Training 工程](../Training/README.md)的实际引擎为 `native_mujoco_bc_v1`。[教程](training.zh-CN.md)展示了 BC → PPO 设置入口，但没有将其标为已经完成的 PPO 训练。网页训练的 9 输入、2 输出模型与[配套实机策略](../policy/README.md)不同，其实机验收仍需单独完成。

与人形机器人的联系，可以表述为同属机器人学习控制的方法范畴。例如 [DeepMimic](https://xbpeng.github.io/projects/DeepMimic/index.html)将动作模仿目标与强化学习结合，[ASAP](https://agile.human2humanoid.com/)展示了人形机器人的动作学习、仿真与实物迁移。不能据此宣称本项目采用了与某款先进人形机器人完全相同的算法或具备相同能力。

### 更准确的第二段备选

> 而让它学会这个动作的，是模仿学习。我们还可以在这个基础上继续做强化学习，体验现在人形机器人研究中也在使用的这类控制方法。

该句作为技术核对后的备选，未替换上方确认的原文。若视频要明确展示“模仿学习加强化学习”的训练成果，应配套提供实际的 PPO 训练与评估记录。

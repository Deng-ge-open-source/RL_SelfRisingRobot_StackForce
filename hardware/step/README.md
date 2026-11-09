# SelfRising 90S · STEP 通用 CAD

简体中文 · English below

下载后用支持 STEP 的 CAD 软件打开。文件使用毫米，包含实体、曲面和装配位置。要打印零件，使用对应的 [STL 打印包](../../SelfRising-90S-STL.zip)。

| 文件 | 内容 |
|---|---|
| [01-base.stp](01-base.stp) | 红色底座 |
| [02-bottom-cover.stp](02-bottom-cover.stp) | 底盖 |
| [03-middle-link.stp](03-middle-link.stp) | 中间连杆 |
| [04-upper-link.stp](04-upper-link.stp) | 上部连杆 |
| [05-spacer-ring.stp](05-spacer-ring.stp) | 轴套 |
| [SelfRising-90S-assembled.stp](SelfRising-90S-assembled.stp) | 整机装配，包含两只舵机的参考几何 |

六个文件均从设计者修改后的原生 CAD 模型导出，采用 STEP AP203 实体表示。已用独立 CAD 内核重新打开检查，五个分件各含一个有效实体，整机含七个有效实体。尺寸与已发布 STL 相差小于 0.01 mm。

[下载 STEP 包](../../SelfRising-90S-STEP.zip) · [分件尺寸](../stl/README.md) · [GPL 正文](COPYING)

五个打印件设计及其 STEP 文件采用 GNU GPL v3.0（`GPL-3.0-only`）。整机中的外购舵机几何用于安装参考，其来源单独记录。使用 `SHA256SUMS` 核对文件完整性。

## English

Open these files in a CAD application that supports STEP. Units are millimetres. The files preserve solid geometry and assembly placements. For slicing, download the corresponding [STL print pack](../../SelfRising-90S-STL.zip).

The table above contains the base, bottom cover, middle link, upper link, spacer ring and complete assembly with two servo references. All six files were exported directly from the designer's modified native CAD model as STEP AP203 solids. Independent CAD reimport verified one valid solid in each printable part and seven valid solids in the assembly. Bounds match the published STLs within 0.01 mm.

[Download STEP pack](../../SelfRising-90S-STEP.zip) · [Dimensions](../stl/README.md) · [GPL text](COPYING)

The five printable designs and their STEP files use `GPL-3.0-only`. Purchased servo reference geometry in the assembly has separate provenance. Check file integrity with `SHA256SUMS`.

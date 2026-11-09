# SelfRising 90S · STL 打印文件

简体中文 · English below

打印时使用五个编号分件，以 **毫米、100% 比例**导入切片器。底座和底盖用红色，连杆和轴套用白色。整机文件用于查看装配位置。

| 分件 | 名称 | 外接尺寸 X × Y × Z（mm） | 通用 CAD |
|---|---|---|---|
| [01-base.stl](01-base.stl) | 底座 | 60.00 × 60.00 × 40.60 | [STEP](../step/01-base.stp) |
| [02-bottom-cover.stl](02-bottom-cover.stl) | 底盖 | 60.00 × 2.50 × 60.00 | [STEP](../step/02-bottom-cover.stp) |
| [03-middle-link.stl](03-middle-link.stl) | 中间连杆 | 42.18 × 26.00 × 61.00 | [STEP](../step/03-middle-link.stp) |
| [04-upper-link.stl](04-upper-link.stl) | 上部连杆 | 42.18 × 18.00 × 116.00 | [STEP](../step/04-upper-link.stp) |
| [05-spacer-ring.stl](05-spacer-ring.stl) | 轴套 | 3.00 × 10.00 × 10.00 | [STEP](../step/05-spacer-ring.stp) |

五个分件的 STL 均为闭合网格。对应 STEP 采用实体几何，重新导入后的外接尺寸与 STL 相差小于 0.01 mm。

[整机 STL](SelfRising-90S-assembled.stl) · [整机 STEP](../step/SelfRising-90S-assembled.stp) · [下载打印包](../../SelfRising-90S-STL.zip) · [下载 STEP 包](../../SelfRising-90S-STEP.zip)

整机参考包含五个打印件和两只舵机的参考几何，保留装配位置。整机外接尺寸为 60.00 × 60.00 × 180.18 mm。

五个打印件由项目设计者修改，采用 GNU GPL v3.0（`GPL-3.0-only`）。整机中的外购舵机几何用于安装位置参考，其来源单独记录。下载后可用 `SHA256SUMS` 校验文件。[GPL 正文](COPYING)

## English

Import the five numbered parts at **100% scale in millimetres**. Print the base and bottom cover in red and the links and spacer ring in white. Use the assembled model to inspect placement.

| Part | File | Dimensions X × Y × Z (mm) |
|---|---|---|
| Base | `01-base.stl` | 60.00 × 60.00 × 40.60 |
| Bottom cover | `02-bottom-cover.stl` | 60.00 × 2.50 × 60.00 |
| Middle link | `03-middle-link.stl` | 42.18 × 26.00 × 61.00 |
| Upper link | `04-upper-link.stl` | 42.18 × 18.00 × 116.00 |
| Spacer ring | `05-spacer-ring.stl` | 3.00 × 10.00 × 10.00 |

All five printable STLs are closed meshes. Their corresponding STEP files contain solid geometry. Reimported STEP bounds match the STLs within 0.01 mm. The assembly includes five printable parts and two servo references in their saved positions, measuring 60.00 × 60.00 × 180.18 mm.

The project designer's five modified printable designs use `GPL-3.0-only`. Purchased servo reference geometry has separate provenance. Verify downloads with `SHA256SUMS`. [GPL text](COPYING)

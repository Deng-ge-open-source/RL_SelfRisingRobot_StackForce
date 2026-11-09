# SelfRising · 90S 打印件

五个打印件来自项目设计者修改后的 Creo 总装 `2dof_.asm.6`。STL 采用二进制格式，坐标以毫米表示。导入切片器时使用 **mm、100% 比例**。

The five printable parts come from the project designer’s modified Creo assembly `2dof_.asm.6`. Import the binary STLs at **100% scale in millimetres**.

| 文件 | 零件 | 外接尺寸 X × Y × Z（mm） | Creo 来源 |
|---|---|---|---|
| [01-base.stl](01-base.stl) | 底座 · Base | 60.00 × 60.00 × 40.60 | `_x2_5b9e4f53_x0_1.prt.8` |
| [02-bottom-cover.stl](02-bottom-cover.stl) | 底盖 · Bottom cover | 60.00 × 2.50 × 60.00 | `bottom_gap.prt.1` |
| [03-middle-link.stl](03-middle-link.stl) | 中间连杆 · Middle link | 42.18 × 26.00 × 61.00 | `__x2_672a4fdd5b58_x0___2.prt.17` |
| [04-upper-link.stl](04-upper-link.stl) | 上部连杆 · Upper link | 42.18 × 18.00 × 116.00 | `top.prt.4` |
| [05-spacer-ring.stl](05-spacer-ring.stl) | 轴套 · Spacer ring | 3.00 × 10.00 × 10.00 | `_x2_5b9e4f53_x0_2.prt.1` |

每个零件的网格均为闭合体，法向一致。五件的 STL 外接尺寸与 Creo 相差均小于 0.01 mm。连杆的封闭内腔保留自 CAD 原件。`SHA256SUMS` 可校验下载的文件。

舵机作为总装的外购件使用。材料、切片方向及试装公差将在实物复现后写入打印指南。

## 整机参考 · Assembly reference

整机文件按总装保存的零件位置导出，包含两处舵机参考几何。核对装配时打开整机文件，打印时使用表格中的五个分件。 [整机 STL](SelfRising-90S-assembled.stl)

The assembly STL preserves the saved Creo placements and includes both servo references. Open it to inspect the assembled robot, then slice the five individual files listed above. [Assembly STL](SelfRising-90S-assembled.stl)

## 许可与编辑源 · Licence and editable source

GNU GPL v3.0（`GPL-3.0-only`）适用于上述五个打印件的设计及其对应的 Creo 编辑源。整机参考文件含舵机参考几何，其分发许可单独核对。 [GPL 正文](COPYING) · [Creo 编辑源](cad-source/README.txt)

GNU GPL v3.0 (`GPL-3.0-only`) covers the five printable designs and their corresponding editable Creo files. The servo geometry included in the assembly reference has separate provenance. [GPL text](COPYING) · [Editable Creo files](cad-source/README.txt)

# 直接对照源码的逐项 UI 调整 · 2026-10-17

源仓库 `D:/job assistant/data/references/open-claude-ui`，提交 ddf3aea1711db62fd6d24343bbab500a5ae69f64。当前71个受跟踪文件在本地，无缺失；本次unshallow补齐当前分支可达历史，40个提交。不是重新克隆一个空目录，也不声称所有远端分支都已取得。

本轮直接读并适配 `cds-theme.css`、`CdsButton.tsx`、`SegmentedControl.tsx`、`AttachmentCard.tsx`、`ConfirmationDialog.tsx`、`ContainerResponsiveBar.tsx`，接续已采用的滚动、代码复制、媒体与共享转场。参考为社区实现，非官方验证。

## 逐项照改的范围

| 源文件 | 落地 |
| --- | --- |
| cds-theme.css | 两站引入四层表面别名、10%/20%边界、双层投影、8/12/16圆角与微交互曲线；保留既有品牌色与插画 |
| CdsButton.tsx | 主操作实填，次操作浅填充，ghost透明；减少卡片内重复闭合边框；保持已有禁用/加载/权限行为 |
| SegmentedControl.tsx | 岗位统计、题库/阅读标签增加独立轨道和滑块。按真实元素测量，支持不等宽与手机换行，而非假定所有项横向等分。减少动效直接定位 |
| AttachmentCard.tsx | 简历/档案/来源相关区域采用嵌套圆角、轻边界和低层投影；不把课程来源伪装成上传附件，文件名算法未采用 |
| ConfirmationDialog.tsx | 16px圆角、双环弥散投影、2px背景模糊、动态视口高度。保留标题、表单、分区与所有按钮；不照搬其不完整的focus trap |
| ContainerResponsiveBar.tsx | 实际命名容器查询，按当前工作区宽度重排表单、筛选和阅读标签；页面收窄与导航收起都由实际容器决定 |

完整35模块在 `REFERENCE_COVERAGE.json` 中逐项登记。这是按场景适配，不是把音频、macOS窗口、模型Token仪表等无关业务硬塞入两个产品，也不声称35个React组件均已移植。

## 保留与加载入口

求职：`static/index.html` 新增加载 `static/reference-system.css`；`static/surfaces.js` 增加统计滑块测量。现有页面DOM内容未删，工业大标题、荧光导航、统计、引导/导出、岗位卡、插画、表单和操作入口保留。

ENSAM：`src/main.jsx` 新增加载 `src/referenceSystem.css`；`src/useSelectionIndicator.js` 服务现有题库/阅读标签。仅为原有标签添加ref，保留标题、斜切构图、半调纹理、课程插画、全部课程与来源、导航和操作。

两站原有基础样式和素材文件没有改写；布局和外观通过新增适配层调整。本轮没有修改skill。ENSAM既有数据同步与练习库未提交工作不属于本次提交。

## 验证

求职14项测试通过（21.411s），修复旧弹窗样式优先级后页面测试再通过（6.526s）。ENSAM55项单元测试、桌面/手机五个学习界面、选中滑块实际绘制位置、对比度、键盘、焦点、减少动效、复制与图片转场检查通过；隔离构建4.50s。未覆盖公开dist或发布公开站点。

旧对比度测试把CSS Color 4的 `color(srgb ...)` 小数通道误当0–255，报告了假失败；本次改用浏览器canvas归一化后保持4.5:1阈值再检查，通过。设计检测提示的短时滑块width/height动画作用于小型绝对定位伪元素，不改变文档布局；边界alpha、投影与品牌适配色作为本轮设计值记录，而非删除检测结果。

桌面与手机先集中看一批，发现求职旧ID选择器覆盖部分输入/弹窗，再一次性修复并确认。没有删除元素、提交投递、写生产学习数据、发布ENSAM或重打包安装程序。真机触控和完整跨浏览器矩阵仍未验收。

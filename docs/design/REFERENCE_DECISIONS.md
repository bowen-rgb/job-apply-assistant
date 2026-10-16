# 从 UI 参考到求职助手

日期：2026-10-16。依据用户提供的五张图片、排版/间距资料和 [Caho1/open-claude-ui](https://github.com/Caho1/open-claude-ui) 源码，固定版本 `ddf3aea1711db62fd6d24343bbab500a5ae69f64`。

## 当前设计边界

用户要求在原版上改进。原版工业感标题、荧光色、硬边、字标、插画和编号属于产品识别。之前的统一样式改动削弱了这些特点，现已恢复 `0e4e0f3` 的视觉样式，再以独立增量层修正具体问题。参考项目作为交互和工程实现的来源，不能替用户决定更换视觉方向。

## 逐项采用

| 参考内容 | 当前处理 |
| --- | --- |
| 网格和文字层级 | 调整表单间距、事实可读性和手机输入尺寸，保留展示标题和原有构图 |
| 七档滚动淡出 | 已实现；滚动到边界后清除对应淡出，键盘焦点进入时不遮挡 |
| 按动作区分动效 | 按钮释放使用 600/30/1 阻尼模型；面板采用独立的 300ms 轻过渡；均支持减少动态效果 |
| 用户阅读优先于自动跟随 | 用于工作台轮询刷新：保留阅读锚点、表内滚动、展开和焦点状态；当前没有流式聊天 |
| 输入法合成保护 | 已实现岗位筛选的组合输入保护，完成选词后才刷新结果 |
| 语音波形/噪声门/压缩 | 当前没有录音或语音显示流程；没有添加录音权限和音频模块 |
| 光标锚点图片缩放/共享元素过渡 | 当前没有图片画廊；简历和求职信仍使用原文件查看/下载流程，未新增画廊业务 |
| 可拖拽分栏/双击对半 | 当前没有双栏编辑器或预览编辑任务；未增加独立分栏功能 |

参考源码：[主题](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/cds-theme.css)、[滚动边缘](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ScrollFadeContainer.tsx)、[动效预设](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeMotionPresets.ts)、[滚动跟随](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/useClaudeScrollPinning.ts)、[输入法保护](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ChatComposer.tsx)。

## 数值和许可

8px 网格是默认节奏，不是硬性行业规定。截图把 600/30/1 参数的超调写作 4.2%，该版本源码注释为 8.8%；标准二阶模型得到约 8.8%。反馈窗口和严格收敛时间不同，不能直接把参数等同于实测性能。

这是社区实现，其逆向分析声明不等同于官方独立验证。滚动淡出阶梯参考了 MIT 示例，许可见 [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)。按钮响应根据阻尼公式独立实现，无需引入 React 或 Framer Motion。未导入参考项目的专有字体、图标、截图和品牌素材。

复用方法见 [practical-ui-design](../../skills/practical-ui-design/SKILL.md)。仓库保留可分发版本，本机安装副本供其他项目调用；用户提供的参考图片不提交仓库。

# 从 UI 参考到求职助手

日期：2026-10-16。依据用户提供的五张图片、排版/间距学习资料，以及 [Caho1/open-claude-ui](https://github.com/Caho1/open-claude-ui) 的源码。参考固定版本：`ddf3aea1711db62fd6d24343bbab500a5ae69f64`。

## 案例拆解与采用

| 参考原则 | 原有问题 | 本次实现 |
| --- | --- | --- |
| 从案例提取信息层级 | 多轮样式覆盖，标题从 20 到 68px，辅助事实过小 | 统一 32/24/18/16/14/12px 角色；正文 1.55 行高 |
| 网格与留白形成分组 | 18/20/22/26px 等局部数值混用 | 8–48px 间距令牌，模块、组件和内容用不同节奏 |
| 低对比表面阶梯 | 首页和各功能页的强调色、边框、装饰不一致 | 保留深色导航与蓝色操作，统一浅色表面和边框 |
| 让用户找到下一步 | 首页标题装饰较高，小屏导航挤成竖排 | 缩短标题区，保留真实下一步；手机菜单可展开、选择后收起 |
| 按动作调节反馈 | 多轮动画/装饰样式缺少统一语义 | 快速控件反馈、稍慢的面板出现；支持减少动态效果 |
| 滚动边缘与实际位置关联 | 侧栏长内容的边界不明显 | 七档淡出随溢出和滚动位置更新；键盘焦点进入时关闭遮罩 |

源码参考：[主题令牌](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/cds-theme.css)、[滚动边缘](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ScrollFadeContainer.tsx)、[动效预设](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeMotionPresets.ts)。该项目是社区实现，其逆向分析声明不等同于官方设计规范的独立验证。

## 取舍

8px 网格作为布局默认值，允许 4px 微间距、边框、图标和光学校正。手机正文输入保持 16px，标题和密集数据按角色调整，避免把字体表机械套在所有元素上。

当前产品没有录音、图片画廊或可拖拽分栏，因此未增加对应功能或依赖。图片里的物理参数留作场景参考：截图对按钮弹簧写的 4.2% 超调，与该源码版本的 8.8% 注释不同；不能直接当成统一标准或性能保证。当前控件和面板通过原生 CSS 实现反馈，未引入 React、Framer Motion 或第三方运行时代码。

滚动淡出的透明度阶梯参考了 MIT 源码示例，许可声明已加入 [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md)。未导入原项目的字体、图标、截图或品牌素材。

## 可复用方法

方法已收敛成 [practical-ui-design](../../skills/practical-ui-design/SKILL.md)：理解真实任务、拆解参考、形成小型规范、实现相关交互、有界验证。项目保存可分发源码；本机安装副本供其他项目调用。参考图片本身不放入仓库。

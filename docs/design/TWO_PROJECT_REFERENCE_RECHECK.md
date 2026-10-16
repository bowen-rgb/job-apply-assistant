# 两项目参考覆盖复查 · 2026-10-17

**结论：没有全仓采用，也不把“全部文件有去向”称为“全部功能完成”。** 当前参考提交 `ddf3aea1711db62fd6d24343bbab500a5ae69f64`，71个受跟踪文件在本地齐全，浅克隆。35个示例逐项登记如下；这是采用覆盖核验，不是参考库全组件运行认证。源码内容哈希与模块集合一并保存，后续参考升级可核对增删。

本次在上一轮核验基础上重新对照实际代码，补齐已有选择场景的键盘缺口。核验依据包括此前模块浏览记录、本次相关源码深读及实际行为测试；不宣称本次再次逐行阅读全仓。五张图片沿用对话中的内容，两个Temp原文件仍在、三个微信临时原文件不可用。

后续UI设计落地见 [UI设计调整](UI_DESIGN_REFINEMENT.md)：代码复制与ENSAM图片共享转场现已补齐。下表为前一轮核验快照，当前新增项以该文档及覆盖JSON为准。

## 本次发现与修正

- 求职平台：筛选原有选中样式，但缺少aria-pressed/方向键。本次在 `static/app.js` 补齐上下、Home/End、反向回绕、单Tab入口和合成输入保护；仪表跳转触发render也同步语义。未改品牌样式和材料审批。
- ENSAM：语言radio、题库和阅读tab原来只有鼠标切换。本次 `src/choiceNavigation.js` 与 `src/App.jsx` 补齐键盘/回绕/单Tab入口；tab关联面板，原文件动作保留在标题操作区。搜索结果原来错误标作listbox却没有option行为，现按实际按钮列表使用命名region。
- 原参考 `useClaudeRovingFocus` 从index=0向前时targetIndex=-1，进入处理前被排除，不能照搬成“循环已完成”。本次浏览器验证从第一项反向切换到末项。
- skill原来有原则但没有完整参考核验流程，缺少分组选项与逐项目证据。本次增加按需读取的参考核验流程、35模块场景入口、状态定义和明确完成条件。它仍是设计方法，不是35模块生产组件库。

## 35模块与两个项目

“原有能力”不计为参考带来的新增成果。“部分”必须看后半句缺口。“待增强”表示场景真实存在，尚未实现；“未采用”保留选择理由，不能换算为已完成。

| 参考文件 | 求职平台 | ENSAM |
| --- | --- | --- |
| `ArtifactsSplitPaneResizer.tsx` | 不适用：当前无可调宽编辑器分栏 | 待增强：正文/辅助栏现为固定布局，未实现用户拖动调宽 |
| `AttachmentCard.tsx` | 原有能力：简历和材料列表；未采用参考附件卡组件 | 原有能力：来源/原文件入口；未采用参考附件磁贴 |
| `cds-theme.css` | 部分借鉴：间距/层级；保留工业风、插画和强调色 | 部分借鉴：阅读间距/辅助文字；保留钴蓝和课程插画 |
| `CdsButton.tsx` | 原有能力：原生按钮禁用/加载；局部反馈另见动效项 | 原有能力：原生按钮/禁用；未移植参考按钮组件 |
| `CdsMotionEngine.tsx` | 未采用：保留本项目反馈，未引入该演示引擎 | 未采用：保留课程过渡，未引入该演示引擎 |
| `ChatComposer.tsx` | 部分借鉴：app.js 合成输入保护；无聊天输入器 | 部分借鉴：AppHeader 合成输入保护；无聊天输入器 |
| `ChatComposerChin.tsx` | 不适用：无聊天输入工具底栏 | 不适用：共享讨论为静态导入，无聊天输入工具底栏 |
| `ChatMessageBubbles.tsx` | 不适用：当前无实时聊天流 | 原有能力：SharedChatCard 折叠静态讨论；没有气泡聊天组件 |
| `ClaudeAudioPlayer.ts` | 不适用：无音频任务 | 不适用：当前无课程音频播放器 |
| `ClaudeDesktopHeader.tsx` | 不适用：普通浏览器页面 | 不适用：当前网页无macOS窗口控制 |
| `ClaudeMotionPresets.ts` | 部分借鉴：600/30/1按钮；面板为CSS过渡，其余三套未采用 | 部分借鉴：按场景区分直接拖动和面板过渡；四套弹簧未采用 |
| `CodeBlock.tsx` | 原有能力：错误详情pre；未加行号/复制组件 | 待增强：Markdown代码显示已有，代码复制/反馈未做 |
| `ConfirmationDialog.tsx` | 原有能力：native dialog；不是移植参考不完整focus trap | 原有能力：useDialogFocus；图片查看器加native dialog与焦点返回 |
| `ContainerResponsiveBar.tsx` | 原有能力：媒体查询/手机导航；未采用容器查询工具栏 | 原有能力：媒体查询/手机布局；未采用容器查询工具栏 |
| `CoworkAgentCanvas.tsx` | 不适用：无代理协作画布 | 不适用：无代理协作画布 |
| `createClaudeMainWindow.ts` | 不适用：无Electron主进程 | 不适用：当前网页无该Electron主进程 |
| `DraggableSessionList.tsx` | 不适用：档案列表不是聊天会话列表 | 不适用：课程目录不是聊天会话列表 |
| `EpitaxyIframeBridge.tsx` | 不适用：本地工作台不提供iframe跨窗消息桥 | 不适用：原文件访问不需要该iframe消息桥 |
| `LiveMicActivityBars.tsx` | 不适用：无录音/麦克风波形 | 不适用：无录音/麦克风波形 |
| `McpToolDecisionCard.tsx` | 原有能力：材料审批/可信回执由服务端约束；未采用模拟卡 | 不适用：学习站无该MCP工具执行审批 |
| `MediaLightboxViewer.tsx` | 不适用：当前无课程式图片画廊 | 部分借鉴：缩放、平移、死区、双指逻辑、键盘；多图跑道/切换未做；真实触屏未验 |
| `ModelSelectorEffort.tsx` | 不适用：无此模型推理档位接口 | 不适用：无此模型推理档位接口 |
| `ModelSwitcherWithTokenGauge.tsx` | 不适用：无实时Token预算仪表 | 不适用：无实时Token预算仪表 |
| `ReasoningAmbientGlow.tsx` | 未采用：现有运行文字状态满足任务，不新增思考光晕 | 不适用：静态课程阅读无实时模型推理状态 |
| `RichComposerWithMentions.tsx` | 部分借鉴：IME原则；slash/mention无业务场景 | 部分借鉴：IME原则；slash/mention无业务场景 |
| `ScrollFadeContainer.tsx` | 已借鉴：侧栏七档alpha、上下边界/焦点保护 | 已借鉴：目录七档alpha、尺寸/边界/焦点保护 |
| `SegmentedControl.tsx` | 原有能力：筛选按钮；本次补选中语义/键盘，不含滑块弹簧 | 原有能力：阅读/状态标签；本次补键盘，不含滑块弹簧 |
| `StatusIndicators.tsx` | 原有能力：aria-busy/status与错误提示；未移植参考动画 | 原有能力：加载/错误/练习状态；未移植参考状态组件 |
| `StreamingDiffViewer.tsx` | 不适用：材料核对不是代码diff审查器 | 不适用：课程阅读不是代码diff审查器 |
| `tailwind.config.js` | 未采用：保留现有CSS，无Tailwind迁移需要 | 未采用：保留现有CSS，无Tailwind迁移需要 |
| `ThinkingAccordion.tsx` | 原有能力：details展开评审；没有流式思考强制展开 | 原有能力：details教学/讨论；没有流式思考强制展开 |
| `useClaudeRovingFocus.ts` | 本次借鉴：岗位筛选上下/Home/End/回绕/单Tab入口，保留原生按钮 | 本次借鉴：radio/tab左右/Home/End/回绕/RTL/单Tab入口，修正反向边界 |
| `useClaudeScrollPinning.ts` | 部分借鉴原则：工作台轮询保留位置；未移植聊天自动跟随 | 不适用：无流式生成聊天容器，不强制阅读滚动到底 |
| `useClaudeSharedElementTransition.ts` | 不适用：无缩略图到大图的业务入口 | 待增强：当前查看器仅面板过渡，没有共享元素转场 |
| `useRateLimitBackoff.ts` | 未采用：只读工作台定时刷新/超时不是指数退避，投递重试需业务约束 | 待增强：knowledgeProvider读取错误直报；没有有界指数退避；写学习记录不盲重试 |

## 优先保留的缺口

1. ENSAM图片共享元素转场、多图连续浏览：适用，未做；当前锚点缩放不等于已覆盖整个媒体模块。
2. ENSAM代码块复制与失败反馈、只读请求有界退避：有使用价值，未做。读取重试与学习记录写入需分别设计。
3. ENSAM可调阅读分栏：潜在价值，需要验证密度与最小阅读宽度；固定双栏不等于已实现拖拽分栏。
4. 两站只采用部分动效原则，没有完整落地四套弹簧，也没有采用全部容器查询组件。

这些缺口明确保留，本次没有为凑覆盖率改变产品结构。音频、模型仪表、代理画布和macOS窗口缺少业务场景。

## 验证与边界

- 求职平台：`tests.test_surfaces`、`tests.test_workbench`、`tests.test_application_safety` 本次14项通过（21.777s），包括新增筛选首尾回绕、选中语义、Tab退出、IME与既有审批/回执约束。测试拦截API，无真实投递。
- ENSAM：55项单元测试；桌面/手机尺寸原界面回归及新增语言radio/题库tab键盘验证；图片锚点/焦点/IME组件验证；隔离构建。本次均通过，构建4.67s。日志位于 `test-artifacts/reference-recheck-{unit,surfaces,images,build}.log`。首次题库键盘测试未等待异步hashchange提交，修正测试同步后通过，未绕过断言。
- 当前变更不改变两站配色、插画或主布局；不覆盖ENSAM公开部署与已有数据同步工作。
- 手机尺寸不等于真机手势验收；双指硬件体验、跨浏览器完整矩阵、参考源码自身构建不在已通过范围。

## skill验证范围

更新位置：`C:/Users/ROG/.codex/skills/practical-ui-design`；求职仓库 `skills/practical-ui-design` 已同步相同文件。检查格式和引用有效，并核对场景表模块集合与实际35文件一致；将本次缺口用于检查新流程会要求记录什么。尚未进行新会话独立agent行为评估，所以不宣称该skill已通过独立泛化测试。

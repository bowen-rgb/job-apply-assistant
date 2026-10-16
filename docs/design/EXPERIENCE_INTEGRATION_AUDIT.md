# UI 参考吸收核验：当前下载、阅读范围与实际落地

日期：2026-10-17（Europe/Paris）。本报告只改文档，不改应用代码。参考固定版本 `ddf3aea1711db62fd6d24343bbab500a5ae69f64`；我方核验基线 `58ac9eb263f41200e12bfc3e66b7225559acea04`。

## 结论与诚实边界

**当前版本文件下载齐全，但不是完整历史；求职平台已经吸收一部分交互原则，不能说35个示例都已移植或此前已经逐行读懂。**

1. 本次执行 git rev-parse HEAD、git rev-parse --is-shallow-repository、git ls-files 与 Test-Path：参考HEAD正确，71个tracked文件均存在，missing=0，浅克隆=true。仅证明当前提交的受跟踪文件在磁盘；不证明全历史、所有远端分支、未跟踪外部资产、依赖或外链完整下载。
2. code-examples 当前35个文件；README仍用“30个生产级模块”，不能把作者计数或标签当核验结果。[固定源码树](https://github.com/Caho1/open-claude-ui/tree/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples)。
3. 本次系统浏览35个文件的导出、接口、状态、关键事件、参数及相应文档章节；对弹簧/渐隐/音频/滚动/媒体/共享转场/分栏/IME重点读取实现。README、docs索引、v1/v2章节目录和主题相关段落、src/index.ts、package.json、assets说明也已检查。**这不是全仓逐文件逐行精读**：长篇.full.md、storybook全部脚本、每个组件全部JSX/装饰样式未逐行验证，也未运行参考仓库typecheck/构建/全组件浏览器验收。
4. 既有 [REFERENCE_DECISIONS.md](REFERENCE_DECISIONS.md) 证明之前有范围明确的采用记录；本次无法从当前文件反推此前模型究竟读过多少内容。五张原始用户图片未在本研究子任务中重新取得，逐项对照沿用已有图片主题和先前记录；没有宣称本次重新逐像素看图。已知截图数值冲突单列，不补写看不到的图片内容。
5. 源README自称真实反编译取证/生产级还原，这是**作者声明**；本次没有原商业应用产物、取证日志或独立测试，不能升级为官方证明。[README](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/README.md)。

## 对用户素材与交互原则的逐项核对

| 原则 | 参考代码事实 | 求职平台当前实现与范围 | 验证与剩余项 |
|---|---|---|---|
| 排版层级 | 主题与v1/v2字号、密度令牌均存在；版本间数值不同，非单一通用标尺 | static/surfaces.css统一页面标题/分区；static/refinements.css:4把事实正文设14px/1.6；保留原工业风标题、硬边、插画与荧光识别 | 两项现有UI测试覆盖多页面320/768/1440无横溢出；没有证明所有标题/语言均经过人工审美验收 |
| 8px网格 | 参考同时存在4/6/8/12/20/28等尺寸，不支持“一切必须8倍数”的推论 | static/refinements.css:2声明8/16/24/32，表单与导航使用；workbench仍有12/20/22/26等原布局值 | 属部分节奏统一，不是全站8px迁移；需按文字/密度任务决定例外 |
| 七档边缘淡出 | [ScrollFadeContainer.tsx:84](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ScrollFadeContainer.tsx#L84)给真实alpha采样与位置；28px默认 | static/refinements.css:25起移植alpha阶梯；static/surfaces.js:45起仅侧栏检测顶/底，采用24px；focus-within取消遮罩 | 本次浏览器隔离探针验证top/mid/bottom与键盘focus；不是全站所有滚动区域，也不是纯CSS scroll-timeline实现 |
| 合成提示音 | [ClaudeAudioPlayer.ts:74](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeAudioPlayer.ts#L74)创建振荡器/增益并调频；可配外部音效 | 无相应业务模块/未采用 | 当前求职表单无语音模式，不为展示技术引入录音或提示音 |
| 六频段/噪声门/压缩 | [LiveMicActivityBars.tsx:24](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/LiveMicActivityBars.tsx#L24)六段；:126起0.08门限、0.7幂、1.5倍和权重映射高度 | 未采用，无录音/波形流程 | 这是归一化FFT视觉映射，不能称通用8%声音噪声消除或音频压缩器标准 |
| 按钮弹簧 | [ClaudeMotionPresets.ts:61](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeMotionPresets.ts#L61)600/30/1；主题还有15阶linear曲线，非唯一方案 | static/interaction-refinements.js:7起独立二阶公式、29帧220ms、1.5%按压位移；没有引React/Framer | 本次实际pointer down/up产生220ms/29帧动画；reduce动态切换取消动画；未测多硬件帧率/感知品质 |
| 卡片/浮层弹簧 | [ClaudeMotionPresets.ts:72](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeMotionPresets.ts#L72)320/28/1；modal另400/32，局部组件还不同 | 面板只采用300ms CSS减速入场（refinements.css:19），不是该spring | 原则“按动作区分反馈”落地，四套弹簧未完整采用 |
| 轻反馈弹簧 | [ClaudeMotionPresets.ts:83](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeMotionPresets.ts#L83)380/18/1 | 未采用独立点赞/成功弹跳 | 无相应点赞场景；复制成功可未来按需要评估 |
| 重阻尼拖动吸附 | [ClaudeMotionPresets.ts:94](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeMotionPresets.ts#L94)1200/80/0.1 | 未采用 | 当前无可拖拽面板/分栏；不能把普通dialog动画算作重阻尼拖动 |
| 滚动跟随 | [useClaudeScrollPinning.ts:22](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/useClaudeScrollPinning.ts#L22)用户输入释放pin、40px/150ms、跳最新 | static/workbench.js:35-37/70-71保存轮询前阅读锚点、表内scrollTop、展开和焦点 | tests/test_workbench.py实际覆盖轮询后位置；**不是聊天自动跟随**，我方没有流式聊天图钉/回到最新业务 |
| 光标锚点缩放 | [MediaLightboxViewer.tsx:134](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/MediaLightboxViewer.tsx#L134)以pointer为不动点并钳制边界 | 求职平台未新增画廊/图片放大缩放 | 无场景；PDF查看/下载不等于图片Pan/Zoom |
| 4px死区 | [MediaLightboxViewer.tsx:332](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/MediaLightboxViewer.tsx#L332)实际图片拖动Math.hypot门限；侧栏也有门限 | interaction-refinements.js:25仅判断按钮pointerdown/up位移<4才播放释放动画 | **不是图片拖拽**，也没有可拖动图片业务；该按钮门限只限制动效，未声明会阻止click事件 |
| 共享元素转场 | [useClaudeSharedElementTransition.ts:88](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/useClaudeSharedElementTransition.ts#L88)API检测、reduced motion、视图名称和几何清理 | 未采用 | 无画廊源缩略图→大图场景；普通淡入不算共享元素 |
| 可拖拽分栏/对半 | [ArtifactsSplitPaneResizer.tsx:56](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ArtifactsSplitPaneResizer.tsx#L56)direct设0.5，pointer capture、最小宽度和Escape | 未采用 | 没有材料双栏编辑器；参考自身声明与实现有差距，见下一节 |
| IME | [ChatComposer.tsx:77](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ChatComposer.tsx#L77)合成/native/229守卫；富输入另有WebKit500ms保护 | static/app.js:23、286-287、420-422，岗位筛选合成期阻止render，compositionend再过滤 | tests/test_surfaces.py:69-78验证合成期间含后台render不改列表、结束后过滤；不是已覆盖所有表单Enter/WebKit500ms竞态 |

我方实际加载入口可见 static/index.html:15、304-305，因此上述增量CSS/JS属于已加载运行代码，而非只有文档或未引用示例。

## 图片、源码、注释和实际数值冲突

- 先前图片记录把600/30/1的超调标作4.2%；固定源码注释写8.8%，二阶阶跃模型取阻尼比30/(2√600)≈0.612得到约8.8%。应采“参数+模型估计+实际测试”分别表达，不能把220ms反馈窗口当严格收敛时间。[ClaudeMotionPresets.ts:57](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeMotionPresets.ts#L57)；我方interaction-refinements.js头部已明确220ms为自定反馈窗口。
- 参考v1第8章决策树把SPRING_SNAPPY标签配600/30、BOUNCY配380/18、GENTLE配320/28；真正导出分别为BOUNCY=600/30、SNAPPY=320/28、GENTLE=380/18。因此按参数与导出核对，不能只复制文档名称。[v1指南](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/docs/v1/08-AI-Agent-前端-UI-与动效开发指南.md#L87)。
- ScrollFadeContainer注释把alpha“0d”混同.15：实际0d/255≈5%、26≈15%、4d≈30%、80≈50%、b3≈70%、d9≈85%；.15/.30等是**位置**比例，不是相同alpha。其orientation声明both，但maskStyle只有vertical/horizontal，both返回{}。[ScrollFadeContainer.tsx:11](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ScrollFadeContainer.tsx#L11)；[ScrollFadeContainer.tsx:135](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ScrollFadeContainer.tsx#L135)。
- 分栏注释声称4px门限、左右边缘折叠、双击弹簧回半；实现pointerdown即激活、move无4px判断、只rightCollapsed、双击直接setSplitRatio(.5)。所以它是有用参考，不能原样当验收合格库。[ArtifactsSplitPaneResizer.tsx:56](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ArtifactsSplitPaneResizer.tsx#L56)。
- ConfirmationDialog声明焦点陷阱，但实际只监听Escape，未见Tab循环、初始焦点和返回焦点机制；不能仅凭role=dialog认定完整无障碍。[ConfirmationDialog.tsx:58](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ConfirmationDialog.tsx#L58)。
- v2 CdsMotionEngine标“1.32x Overshoot”，激活用scale-125；CoworkAgentCanvas用默认数组且未见BroadcastChannel；StreamingDiffViewer主要解析/渲染diff，未见ShadowRoot/Worker；McpToolDecisionCard用timeout模拟完成。以上均不否认演示价值，只限制其“生产级系统”声明。[CdsMotionEngine.tsx:12](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/CdsMotionEngine.tsx#L12)；[CoworkAgentCanvas.tsx:93](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/CoworkAgentCanvas.tsx#L93)；[StreamingDiffViewer.tsx:125](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/StreamingDiffViewer.tsx#L125)；[McpToolDecisionCard.tsx:59](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/McpToolDecisionCard.tsx#L59)。

## 35个代码示例的系统浏览清单

这里“浏览”指核对接口、主要状态与事件、关键实现，**不表示每行样式精读或所有运行行为已测**。重点算法深读范围见上表。

| 文件 | 本次核对内容 |
|---|---|
| [ArtifactsSplitPaneResizer.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ArtifactsSplitPaneResizer.tsx#L1) | 分栏比例、pointer capture、Escape回滚；实现不等于注释的死区/弹簧，见下文 |
| [AttachmentCard.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/AttachmentCard.tsx#L1) | 文件类型、磁贴/胶囊、文件名中截断；不是文件上传服务 |
| [CdsButton.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/CdsButton.tsx#L1) | 尺寸/变体、disabled、loading与CSS形变，不是统一业务权限 |
| [CdsMotionEngine.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/CdsMotionEngine.tsx#L1) | v2演示组件；标注1.32但激活类scale-125实际目标1.25 |
| [ChatComposer.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ChatComposer.tsx#L1) | 输入框自增高、IME、附件本地状态；有模拟添加附件 |
| [ChatComposerChin.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ChatComposerChin.tsx#L1) | v2输入底栏与工具容器 |
| [ChatMessageBubbles.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ChatMessageBubbles.tsx#L1) | 用户/助手正文、折叠、复制、附件与工件展示 |
| [ClaudeAudioPlayer.ts:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeAudioPlayer.ts#L1) | Web Audio合成四类提示音，可指定外部音效文件 |
| [ClaudeDesktopHeader.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeDesktopHeader.tsx#L1) | macOS标题栏占位与Electron桥接依赖 |
| [ClaudeMotionPresets.ts:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeMotionPresets.ts#L1) | 二阶求解器、四套弹簧、消息/Popover/modal变体 |
| [CodeBlock.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/CodeBlock.tsx#L1) | 行号、复制反馈、2.5s状态复位 |
| [ConfirmationDialog.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ConfirmationDialog.tsx#L1) | Escape/遮罩关闭/role=dialog；注释承诺focus trap但未见trap实现 |
| [ContainerResponsiveBar.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ContainerResponsiveBar.tsx#L1) | 容器查询分档隐藏/布局调整 |
| [CoworkAgentCanvas.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/CoworkAgentCanvas.tsx#L1) | 默认代理/工件演示数据；注释说BroadcastChannel，组件未见真实通道 |
| [DraggableSessionList.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/DraggableSessionList.tsx#L1) | 本地session列表、固定/拖动/键盘；不等于真实会话持久服务 |
| [EpitaxyIframeBridge.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/EpitaxyIframeBridge.tsx#L1) | iframe sandbox、source/origin过滤、message路由；用户激活hasBeenActive不能单独证明当前动作授权 |
| [LiveMicActivityBars.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/LiveMicActivityBars.tsx#L1) | 六段FFT、0.08门限、0.7幂、1.5倍与权重、RAF；偏视觉能量映射 |
| [McpToolDecisionCard.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/McpToolDecisionCard.tsx#L1) | 本地授权卡状态演示；用setTimeout模拟完成，不是真实MCP后端 |
| [MediaLightboxViewer.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/MediaLightboxViewer.tsx#L1) | 光标锚点缩放、4px平移门限、wheel、焦点与键盘 |
| [ModelSelectorEffort.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ModelSelectorEffort.tsx#L1) | 五档推理选项展示与回调，非模型能力探测 |
| [ModelSwitcherWithTokenGauge.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ModelSwitcherWithTokenGauge.tsx#L1) | 模型/effort选择和Token仪表盘，内置模型数据非实时服务 |
| [ReasoningAmbientGlow.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ReasoningAmbientGlow.tsx#L1) | 晕染/扫光/三点/canvas动效 |
| [RichComposerWithMentions.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/RichComposerWithMentions.tsx#L1) | slash/mention、IME和WebKit500ms保护；默认建议数据 |
| [ScrollFadeContainer.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ScrollFadeContainer.tsx#L1) | vertical/horizontal渐隐、ResizeObserver；both分支没有mask |
| [SegmentedControl.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/SegmentedControl.tsx#L1) | 受控/内部选中、移动指示器，局部spring=500/35 |
| [StatusIndicators.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/StatusIndicators.tsx#L1) | 状态灯/呼吸/运行脉冲/骨架 |
| [StreamingDiffViewer.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/StreamingDiffViewer.tsx#L1) | parseGitDiff与统一/分屏布局；未见注释所述ShadowRoot/Worker增量服务 |
| [ThinkingAccordion.tsx:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ThinkingAccordion.tsx#L1) | 生成时强制展开、用户折叠和复制 |
| [cds-theme.css:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/cds-theme.css#L1) | 字体/色彩/密度/圆角/响应时间/关键帧；v1/v2概念混排需逐条选用 |
| [createClaudeMainWindow.ts:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/createClaudeMainWindow.ts#L1) | Electron窗口和WebContentsView、macOS交通灯坐标，不适用当前普通网页 |
| [tailwind.config.js:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/tailwind.config.js#L1) | 主题与Tailwind扩展；我方无React/Tailwind迁移必要 |
| [useClaudeRovingFocus.ts:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/useClaudeRovingFocus.ts#L1) | 方向键/Home/End/RTL与tabIndex |
| [useClaudeScrollPinning.ts:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/useClaudeScrollPinning.ts#L1) | 40px底部阈值、150ms用户输入保护、120px显示跳转 |
| [useClaudeSharedElementTransition.ts:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/useClaudeSharedElementTransition.ts#L1) | ViewTransition命名配对、圆角/object-fit inset和降级/清理 |
| [useRateLimitBackoff.ts:1](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/useRateLimitBackoff.ts#L1) | 指数退避/重试状态和计时器；业务执行可靠性仍由调用方负责 |

相关文档浏览范围：中文README的项目定位/入口，docs/README与v1/v2导航，v1第1章排版/表面与边框、第2章控件/附件、第3章输入与IME、第4章弹簧/渐隐、第5章音频/媒体/分栏、第6章滚动/容器/焦点，第7章代码清单/资产，第8章决策树；v2各章标题与相关密度/24px渐隐/触控补偿/示例段落。README-en仅核对文件存在，未单独精读。没有验证作者对Claude专有运行时、47种动效、反编译包位置和商业版本演进的完整叙述。

## 本次实际运行验证

- 素材范围：五张图片的内容均保留在本对话中；本次检查本地附件时，两张 Temp 图片仍存在，三张微信临时图片已不存在。因此没有声称本次重新打开了全部五个原始文件。
- 补充运行 `tests.test_application_safety`：12项通过，6.008s。材料审批与可信投递回执的业务约束仍由服务端测试覆盖，界面反馈不能代替真实审批或投递成功。
- 命令：`.venv/Scripts/python.exe -m unittest tests.test_surfaces tests.test_workbench -v`。
- 结果：2项测试通过，17.823s。合成接口/数据在Playwright route拦截，未连接真实求职平台、未真实投递。覆盖现有页面/导航/移动宽度/六语/合成输入与轮询位置等测试断言，不能由两项测试推导所有交互完成。
- 额外只读浏览器隔离探针加载当前refinements.css、surfaces.js、interaction-refinements.js，构造可溢出侧栏（maxScroll=570）：顶部flags=false/true，中间true/true，底部true/false；焦点进入mask=none；按钮产生duration=220、frames=29，开启减少动效后动画数0。**这验证当前模块在受控fixture中生效，不替代真实整页所有内容尺寸/浏览器/触屏验收。**
- 第一次探针的测试容器未强制按钮块排，未形成预期滚动，断言失败；修正fixture为固定溢出后通过，未改应用。此项不作为应用缺陷。
- 业务测试按原测试会更新data下预览截图；没有修改产品代码、真实profile、投递台账或第三方服务。

## 给下一项前端改造的约束

1. 先找已有业务场景和品牌识别，再选择参考。例如另一前端若已有单张图片适屏层，可接入锚点缩放、拖拽、触屏/键盘和焦点返回；不能把求职平台按钮4px反馈拿来宣称已实现。
2. 每项建立“原场景→真实源码→采用差异→行为断言”；保留减少动效、焦点和IME保护。
3. 不因为参考自称完整就整体迁移React/Framer，也不为普通求职表单添加音频/聊天/分栏。
4. 下次诚实表述：“已取得当前提交、系统浏览全部示例并重点核查相关算法，已在对应场景落地且测试的项列在清单；其余未采用或未验证。”不要说“已完整读懂所有素材并全部吸收”。

许可归属已保存在 [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md) 的 Caho1/open-claude-ui 段落；当前主要代码适配为滚动alpha阶梯，其他布局/按钮由本项目独立实现。

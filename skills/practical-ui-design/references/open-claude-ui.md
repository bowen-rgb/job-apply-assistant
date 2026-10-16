# open-claude-ui 的适用性提示

固定源：[Caho1/open-claude-ui @ ddf3aea](https://github.com/Caho1/open-claude-ui/tree/ddf3aea1711db62fd6d24343bbab500a5ae69f64)。该提交的 `code-examples` 有35个文件，README 标30；版本变化时重新盘点。以下是审阅入口，既不要求全部移植，也不表示参考全部通过生产验证。

| 场景 | 需考虑的参考文件 | 决策/验收重点 |
| --- | --- | --- |
| 控件与选择 | CdsButton、SegmentedControl、useClaudeRovingFocus | 加载/禁用/选中；方向键首尾回绕、RTL、Tab退出。原参考从第0项向前得到-1时判定有边界缺陷，适配时单独验证 |
| 动效与状态 | ClaudeMotionPresets、CdsMotionEngine、ReasoningAmbientGlow、StatusIndicators | 按操作选择反馈；减少动效、运行状态真实；不为静态操作添加无限思考动画 |
| 输入 | ChatComposer、ChatComposerChin、RichComposerWithMentions | IME、增高、附件、建议；已有搜索可采用IME，不能据此声称已有完整聊天输入器 |
| 文本与讨论 | ChatMessageBubbles、CodeBlock、ThinkingAccordion、StreamingDiffViewer | 复制成功/失败、长文本、折叠与读者控制；已有静态讨论不等于实时聊天，课程阅读不等于代码diff审查 |
| 滚动与响应式 | ScrollFadeContainer、useClaudeScrollPinning、ContainerResponsiveBar | 实际溢出/尺寸变化、停止自动跟随、焦点不遮挡；媒体查询不等于采用容器查询 |
| 媒体 | AttachmentCard、MediaLightboxViewer、useClaudeSharedElementTransition | 文件状态、锚点缩放/边界、4px拖动、图库切换、缩略图转场；将子能力分别登记 |
| 音频 | ClaudeAudioPlayer、LiveMicActivityBars | 仅实际播放/录音产品适用；FFT视觉映射不是通用降噪标准 |
| 对话框与工具 | ConfirmationDialog、McpToolDecisionCard、useRateLimitBackoff | 焦点限制/返回、授权来源、结果真实、幂等；模拟setTimeout不等于后台已完成 |
| 桌面与分栏 | ArtifactsSplitPaneResizer、ClaudeDesktopHeader、createClaudeMainWindow | 现有双栏是否需要用户调宽；键盘替代、释放/取消、最小宽；浏览器不需macOS窗口控制 |
| 会话、协作与嵌入 | DraggableSessionList、CoworkAgentCanvas、EpitaxyIframeBridge | 有无真实会话/通道/iframe；权限、来源过滤、持久化；普通课程目录不同于会话列表 |
| 模型设置 | ModelSelectorEffort、ModelSwitcherWithTokenGauge | 有无真实模型/预算接口，避免展示假Token/模型能力 |
| 主题与工程 | cds-theme.css、tailwind.config.js | 学习层级/密度，保留目标品牌；无需为借鉴迁移整个技术栈 |

## 该固定版本已知的说明/实现差异

- 600/30/1标准二阶模型超调约8.8%；用户截图写4.2%。收敛时长取决于阈值，不能把0.22s当通用保证。
- 动效指南的预设名称和导出参数存在对调，按参数与实际行为核对。
- ScrollFadeContainer 的 both 分支没有 mask；阶梯停靠位置和alpha值不同，见 [interaction-patterns.md](interaction-patterns.md)。
- 分栏注释提4px、双边折叠、弹簧复位，实际实现不能全部支持这些声明。
- ConfirmationDialog 的role/Escape不足以构成焦点陷阱；独立测试 Tab 与关闭返回。
- 部分代理画布、MCP卡、diff组件是演示状态；注释中的BroadcastChannel、Worker或服务端执行不能当作已实现。

版本升级后以上差异都需重新核对。具体项目的采用清单放项目自身设计记录，避免 skill 缓存项目状态后失真。

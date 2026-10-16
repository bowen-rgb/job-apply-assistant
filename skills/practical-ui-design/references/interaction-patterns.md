# 按场景选择交互

用户提供的图片是设计参考，不是产品授权或官方参数证明。下面的源码参考来自社区项目 [Caho1/open-claude-ui](https://github.com/Caho1/open-claude-ui/tree/ddf3aea1711db62fd6d24343bbab500a5ae69f64)，固定版本 `ddf3aea1711db62fd6d24343bbab500a5ae69f64`。

## 滚动区

适合侧栏、消息和预览，采用边缘淡出提示还有内容。无溢出时关闭；触顶取消顶部淡出，触底取消底部淡出；内容和容器尺寸改变后重算。键盘焦点进入时保证文字和焦点完整可见。优先页面自然滚动，避免为了动效制造嵌套滚动。

参考：[ScrollFadeContainer.tsx](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ScrollFadeContainer.tsx)。七档非线性透明度是可选视觉方案；没有必要把所有滚动区都遮罩。

## 动效

按动作语义区分反馈：按压快速，面板出现稍慢，连续拖动直接跟随指针。普通任务界面可先用约 120ms 的控件反馈、220ms 的状态反馈、300ms 的面板过渡作为试调起点；实际时长依内容和硬件验证。动画期间控件仍可操作。尊重 `prefers-reduced-motion`。

已有弹簧引擎时，可研究 [ClaudeMotionPresets.ts](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ClaudeMotionPresets.ts) 的刚度、阻尼、质量分工。仅为少量反馈时，可用原生 CSS/Web Animations，按项目依赖和需求决定。

截图和源码的数值可能不同。例如截图把 `k=600,c=30,m=1` 的超调写为 4.2%，该版本源码注释为 8.8%；标准二阶欠阻尼模型得到约 8.8%。收敛时间还取决于判定阈值。参数、模型估算和设备实测应分别记录，避免宣称一组参数能保证某个精确时长。

## 自动跟随与输入

流式内容只在用户已接近底部时自动跟随；用户主动上滑后停止，提供“回到最新”操作。保留阅读位置，不把轮询刷新变成滚动跳转。参考：[useClaudeScrollPinning.ts](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/useClaudeScrollPinning.ts)。

新增 Enter 提交或快捷键时，检查中文、日文等输入法合成状态，避免确认候选词时误提交。参考：[ChatComposer.tsx](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/ChatComposer.tsx)。

## 图片与拖拽

仅在确有图片浏览需求时实现光标锚点缩放；缩放前后的光标下内容位置保持不变，再按图片/视口边界限制平移。轻微移动不立即视作拖拽；4px 可以作为鼠标的试调起点，触屏另测。提供键盘缩放、复位和关闭操作。

共享元素过渡依浏览器支持渐进增强；关闭时恢复触发位置和焦点，减少动态效果时直接切换。参考：[MediaLightboxViewer.tsx](https://github.com/Caho1/open-claude-ui/blob/ddf3aea1711db62fd6d24343bbab500a5ae69f64/code-examples/MediaLightboxViewer.tsx)。分栏拖拽需要最小宽度、键盘替代操作和指针释放处理。

## 音频

只有产品本来需要录音或播放时，才评估噪声门、压缩和提示音；阈值取决于信号定义、设备和环境。截图中的 8% 和 0.7 次方不能直接当作通用音频标准。不要为普通表单增加录音权限或音频依赖。

## 使用源码

这是社区项目对 Claude 的实现和分析，其自述不等于官方背书或独立验证。借用设计逻辑即可独立实现；实际复制代码时检查并保留许可证声明。素材、字体和品牌标志分别核查使用权。

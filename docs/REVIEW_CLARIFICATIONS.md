# 审核缺项与答案复用

2026-10-31：岗位页批量处理进度增加“查看缺少什么 / 补全信息”。展示每个 HUMAN_REVIEW 的原始理由、问题、岗位链接；新回复须区分候选人事实、企业信息、当前表单和评分异常，并给出对应要求依据。旧结果保留原问题，不猜测分类。ERROR 不混入缺项清单。

个人回答保存在当前候选人 background.review_answers，默认仅对原岗位生效。用户明确勾选个人事实才可跨岗位审核复用；企业条件、表单声明和评分错误不可复用。常用 application.saved_answers 同时进入审核数据。保存不会自动提交申请，底部继续按钮使用原有批量工作流；资料变化会使旧授权失效。

提示词将必需条件和可学习的差距、偏好、可后续核实的细节分开，不因未公布精确地址、薪酬、博士资金等单独阻止准备；真实硬性条件仍保留。候选人事实不得被升级为未证明的精通。

参考实际源码：
- [Apply-Pilot evaluate.mjs](https://github.com/YingQiu0871/Apply-Pilot/blob/main/src/evaluate.mjs)：事实、禁止宣称、评分分离及结构化 gaps。
- [ai-job-search 04-job-evaluation.md](https://github.com/ai-job-search-dev/ai-job-search/blob/master/.claude/skills/job-application-assistant/04-job-evaluation.md)：资格门槛、技能差距与附条件申请的区分。

沿用原生 Python/HTML/JS，不嵌套外部系统；本轮参考设计原则，未复制外部源码。

验证：隔离候选人数据的后端测试，及桌面浏览器真实点击缺项、填写、勾选复用、保存、继续流程。截图 tmp/review-gaps-desktop.png 为模拟资料，不含真实申请材料。

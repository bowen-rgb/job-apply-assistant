# 审核缺项与答案复用

2026-10-31：岗位页批量处理进度增加“查看缺少什么 / 补全信息”。展示每个 HUMAN_REVIEW 的原始理由、问题、岗位链接；新回复须区分候选人事实、企业信息、当前表单和评分异常，并给出对应要求依据。旧结果保留原问题，不猜测分类。ERROR 不混入缺项清单。

个人回答保存在当前候选人 background.review_answers，默认仅对原岗位生效。用户明确勾选个人事实才可跨岗位审核复用；企业条件、表单声明和评分错误不可复用。常用 application.saved_answers 同时进入审核数据。保存不会自动提交申请，底部继续按钮使用原有批量工作流；资料变化会使旧授权失效。

提示词将必需条件和可学习的差距、偏好、可后续核实的细节分开，不因未公布精确地址、薪酬、博士资金等单独阻止准备；真实硬性条件仍保留。候选人事实不得被升级为未证明的精通。

参考实际源码：
- [Apply-Pilot evaluate.mjs](https://github.com/YingQiu0871/Apply-Pilot/blob/main/src/evaluate.mjs)：事实、禁止宣称、评分分离及结构化 gaps。
- [ai-job-search 04-job-evaluation.md](https://github.com/ai-job-search-dev/ai-job-search/blob/master/.claude/skills/job-application-assistant/04-job-evaluation.md)：资格门槛、技能差距与附条件申请的区分。

沿用原生 Python/HTML/JS，不嵌套外部系统；本轮参考设计原则，未复制外部源码。

验证：隔离候选人数据的后端测试，及桌面浏览器真实点击缺项、填写、勾选复用、保存、继续流程。截图 tmp/review-gaps-desktop.png 为模拟资料，不含真实申请材料。

## 自动查证补全（2026-10-31）

发现旧实现未传入通勤起点，并禁止 ChatGPT 浏览网页。现在审核包包含当前档案地址字段（不包含邮箱、电话）；提示词允许查证原始岗位、机构地址和公共交通来源。确切地址缺失但城市位于允许范围内时，粗略交通判断不能冒充门到门验证，也不因精确时长未知单独阻止准备。

批量复核第二轮前调用原生 review_research.collect；旧 HUMAN_REVIEW 再审也进入该步骤。复用已有搜索、受限公开 GET 和已内化的 ai-job-search posting_guard 清洗源码。最多保存两页正文，搜索摘要仅用于发现链接，不作为证据。公开证据按岗位内容指纹缓存 24 小时，失败缓存 15 分钟；搜索和缓存不包含家庭地址。页面不可访问记录为 unavailable，交给 ChatGPT 的可用浏览能力继续查证，不能捏造答案。历史疑问进入新审核上下文，而不是原样重复同一提示。

研究结果随岗位 review_json 保存，含来源网址、依据和 verified/estimate/unavailable 状态，在岗位详情和补全窗口可查看。网页来源仍是不可信数据；模型声称 verified 不等同于本地独立事实核验。交通时长须标注路线、时间假设和估算性质，不把驾车时间当公交时间，不把个人同意或招聘方承诺进行跨岗位复用。

具体参考：ai-job-search 的 09-web-research.md（原页优先、失败后官网替代、摘要不当证据）及 04-job-evaluation.md（研究缓存与事实核验分开）；Apply-Pilot 的 evaluate.mjs（事实/缺口/评分结构）。两仓库均未提供可直接复制的公共交通门到门查询器，未声称已接地图实时路线 API。

验证：41 项相关测试通过；CEA 42103 公开来源抓取试跑获取两页、无读取错误。该验证不等同于完整 ChatGPT 在线复核或真实通勤验证；没有发送申请。

## 旧缺项的一键自动补全

批量状态和补全窗口均提供“让 ChatGPT 自动补全并再审”。请求 /api/matches/automation?mode=clarify 固定本次仍符合资格的 HUMAN_REVIEW 岗位集合，走现有后台 worker 的查证、审核、通过后入队流程。失败重试保留原集合（包括刚因连接错误成为 ERROR 的当前项），不会混入全部未审核岗位；已投递、跳过、明确否决、失效及已入队仍受原筛选约束。后台运行期间重复点击不另开任务。资料或岗位变化仍需重新验证授权。

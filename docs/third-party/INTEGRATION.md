# 求职工作流整合记录

2026-10-30。目标：复用实现和工作方法，保持一个本地应用、一个候选人档案系统、一份 SQLite 申请记录。没有嵌套上游页面，没有运行第二个服务，没有安装上游 Claude/Codex 命令框架，没有新增 Python/npm 运行依赖。

## 固定阅读版本与源码许可

* [ai-job-search](https://github.com/ai-job-search-dev/ai-job-search/tree/83c788d779b74522bb346145ef675b984bf2d3f7)，MIT，Copyright (c) 2026 Mads Lorentzen。
* [Apply-Pilot](https://github.com/YingQiu0871/Apply-Pilot/tree/a15485ee35421fa3103efe696f8cb1c072195d59)，MIT，Copyright (c) 2026 Yuning Gu。

直接复用：`app/vendor/job_search/posting_guard.py`、`page_decode.py`。保留完整 MIT LICENSE；只把脚本目录导入改为 Python 包相对导入。解析岗位的真实路径调用 guard，而不是放着未使用的副本。隐藏文本、不可见字符不进入岗位正文；审计计数进入 structured_json。启发式识别不是完整安全保证。

移植适配：Apply-Pilot 的 `src/followups.mjs`、`events.mjs`、`scoring.mjs`、`keywords.mjs`、`importer.mjs`、`scan/portals.mjs` 的核心机制，分别进入 `application_intelligence.py`、`tracker_exchange.py`、`portal_feeds.py`。上游完整许可保存在 [Apply-Pilot-LICENSE.txt](Apply-Pilot-LICENSE.txt)。移植的变化包括严格数值校验、结构化事件、数据库事务、候选人隔离、HTTPS/公开网络检查及分页预算。

工作流参考：ai-job-search 的 `/apply`、`/outcome`、`/gmail-sync`、`/rank`、`/interview` 与评估规则。没有把这些提示词当成工程指令执行，也没有把示例候选人事实写入共享代码。

## 逐项对照与落点

| 优点 | 本项目落实情况 | 入口 / 实现 |
| --- | --- | --- |
| 一份持续维护的申请账本 | 使用现有 jobs、application_stage_events，避免另建 Markdown 真源 | 申请队列与原有跟踪栏 |
| 拒信、面试、录用意向分开 | 已有阶段保留；补邮件信号识别、原文证据和人工确认 | 申请队列 → 招聘反馈与下一步 |
| 收件确认不冒充面试 | ack 独立；仅确认后可把未记录的真实投递补到账本 | mail_outcomes / application_insights repository |
| 不把沉默、抓取失败当成被拒 | 跟进提醒与拒信分开，不修改岗位有效性 | followup_status |
| 按最近真实联系提醒 | 默认 14 天、最多跟进一次，可按档案修改；记录已发跟进后重新计算 | 跟进规则 / 我已发送跟进 |
| 区分邮件与招聘门户跟进 | 沿用真实来源，不凭一个 URL 编招聘联系人 | 到期跟进卡片 |
| 邮件增量、分页、幂等 | 完整正文识别，排除发件/草稿/垃圾，保留归档邮件；消息 ID 去重，分页游标按邮箱与查询隔离 | mail_outcomes.py |
| 模糊关联不猜测 | 同公司多岗位须匹配具体标题；不能唯一确定则待人工处理 | 待确认反馈中的冲突说明 |
| 变更先预览再确认 | 确认批次原子事务；申请阶段变了则拒绝旧提议 | mail-confirm API |
| 硬条件与模型分数分开 | 继续使用现有 constraints / scoring / PFE guardrails | 原有扫描与复核 |
| 固定权重评分 | 可选候选人维度；ChatGPT 给 0–5 分，本地计算；缺项或低于阈值不得直接建议投递 | 跟进规则 → 评分维度；原有复核详情 |
| 诚实的能力与缺口 | 继续使用 skill_inventory、LM01–LM12、事实证据审稿，不把团队技术或学习目标冒充掌握 | 现有简历 / 复核 / 动机信流程 |
| 简历关键词覆盖 | 新增实际所选 CV 文本检查；排除不在岗位原文里的“关键词”；不编辑原简历 | 准备面试／检查简历 |
| 比较多份 CV 的实际证据 | 复用现有 rank_resumes，展示每份证据与得分，明确当前实际路由的 CV | 申请准备资料 |
| 面试准备 | 已提供岗位、CV 证据、STAR 准备框架和向招聘方提问的清单；不生成虚构经历 | 申请准备资料 |
| 原始招聘页与来源证据 | 沿用现有 extractor、PFE 原页核验、source_variants，不另设“已核验”真假标准 | 原岗位卡片 / PFE |
| 12 种 ATS 公开采集 | 扩展到 Workday、SmartRecruiters、Eightfold、Phenom、SuccessFactors、Personio、Greenhouse、Lever、Ashby、Teamtailor、Recruitee、Workable | 原公司 boards 配置；QR 官网抓取复用同一读取器 |
| 来源自动积累 | 原记忆来源记录扩展到可识别 ATS，记公司 board 而不是每条详情页 | pfe.board_from_url / remembered_boards |
| 多语言、按方向搜索 | 继续使用既有 PFE 查询计划、JobSpy、Bing/DDG、可配置 SearXNG、学校与科研渠道 | 原扫描入口与 PFE 配置 |
| 多来源去重 | 保留现有 canonical / fingerprint / title-company-location 合并；导入另检查相似岗位 | 现有 discovery 与导入预览 |
| 旧账本迁移 | CSV/TSV/JSON/Markdown/XLSX，中文/法语/英语列名识别，先预览、只追加、避免覆盖 | 导入／导出申请记录 |
| 可带走的数据 | JSON/CSV/Excel 跟踪账本，保留原 HTML/Excel 人工核验导出 | 原导出 + 新账本导出 |
| 动机信质量和独立审稿 | 保留比上游通用套话检查更细的现有 LM 规则、8 项独立审稿和 PDF 检查；本轮不改生成事实 | LETTER_QUALITY_RULES.md |
| 本地安装、数据与账号隔离 | 继续使用本项目桌面宿主、候选人目录、加密账号、专用 Chrome | 原安装包 / 档案选择 |
| 自动投递 | 保留现有 auto_submission 和提交回执，不用上游“记为 Applied”替代真实网站成功 | 原投递引擎、QR 与队列 |

## 完整能力扩展（2026-10-30 后续轮次）

上一轮暂缓的能力已改为原生实现，不再是“以后再做”的清单。使用入口、配置与逐项说明见 [完整求职工具](../CAREER_TOOLS.md)，验收见 [FULL_CAPABILITY_PLAN.md](FULL_CAPABILITY_PLAN.md)。

| 上游功能 | 本项目实现 |
| --- | --- |
| /setup、/expand，行为与目标画像、潜在职业方向 | career_intelligence.profile_expand、capability_actions.accept_plan；批量导入、证据确认、偏好配置；采用的查询词进入原扫描 |
| /apply 的逐岗 CV、起草／独立审稿、相关性裁切 | career_intelligence.tailor_cv；原件保留、逐句证据、PDF 检查、版本指纹、单岗采用；既有自动申请及 LM01–LM12 保留 |
| /add-template | document_templates；DOCX、TeX、Typst、PDF、ZIP；本地文档编译器和占位符，不执行模板安装脚本 |
| /add-portal | portal_registry；模型分析公开页面，提案经真实查询测试后才可启用，无动态 Python 插件 |
| /interview、模拟面试、/upskill | 联网来源、STAR 原文、分环节准备、持续问答、技能缺口与学习计划；计划不变成技能事实 |
| /outcome、档案、经验校准、/html-report | 原申请历史，加 hired／offer_declined、ZIP 归档、候选人经验提案、离线 HTML 跟踪表；拒信仍需真实证据确认 |
| /notion-sync | Notion 新版 data-source API、目标确认、单向去重、限流处理，原账本为真源 |
| 薪资工具 | 直接使用上游 salary_lookup 校验／公司索引查询，加同口径样本分位数和原生图表 |
| scan boards / websearch、各国示范来源 | extended_sources；Brave、Mojeek、Adzuna、Jooble、Careerjet、France Travail API、JobTech、Euraxess、freehire、丹麦四站、LinkedIn public；原 Bing/DDG/SearXNG/JobSpy/ATS 保留 |
| LinkedIn login / scan / triage | linkedin_discovery；复用专用 Chrome，只操作新建搜索页，岗位与帖子分开，人工选择后加入未核验机会 |
| agent 选择／委托、eval prompt / score / run / pipeline | model_backends、原 bridge、capability_worker、app.cli；Chrome、兼容接口／DeepSeek、Anthropic、Ollama、Claude/Codex/OpenCode CLI |
| followups、draft | 到期规则保留；生成草稿、原邮件会话校验、可选 Gmail compose、明确确认发送、结果不明锁重试 |
| DOCX、lint、SQLite / folder / merge-additions / export | 原生模板段落复制、writing_lint、多文件／目录追加导入、JSON/CSV/XLSX/Markdown/HTML 导出；不覆盖旧记录 |
| doctor、reset、数据目录／桌面启动 | app.cli、现有桌面宿主和 JAA_WORKSPACE_HOME；预览和含二进制材料／数据库 SQL 的重置前备份；保留账号 |

新增直接复用：`app/vendor/job_search/{verify_pdf,verify_layout,salary_lookup}.py`；保留上游 MIT 许可。移植 Apply-Pilot 的 lint、docx、scan/boards、scan/linkedin、agents、importer、scoring、events、followups 机制，完整许可仍保留在 Apply-Pilot-LICENSE.txt。

这里吸收的是可用能力和源码算法，不把上游 Claude 配置、安装器、Node 服务、网站主题或 CI 模板再嵌套进产品。默认 ChatGPT 工作流和本项目所有业务页面保留；可选 career-ops 数据互通通过标准账本交换实现，不运行第二份申请真源。

## 使用与验证边界

入口是 **材料与助手**。扩展能力未配置时显示待配置／缺失原因。没有自动替用户申请云密钥、启用付费调用、发送申请或写入 Notion。Gmail 读取与撰写权限分开；升级需自行重新 OAuth 授权。

来源样本和假模型测试证明解析、路由、校验、状态和确认链有效，不能冒充各平台全部在线可访问。原有 12 ATS、二维码、材料授权、队列、菜单与桌面回归继续运行。真实企业页面、字段和登录可能变化，须以本机连接检查及原文为准。

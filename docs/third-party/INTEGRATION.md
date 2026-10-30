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

## 尚未实现为本项目功能的上游附加能力

这些已阅读，但**不宣称已完成**，也不因为复制了文件就标记“接入”。

| 能力 | 状态 / 不盲目引入的理由 |
| --- | --- |
| ai-job-search 的完整逐岗 CV 重写、LaTeX/Typst 自定义模板注册、版面空洞测量和裁切优化 | 本轮只诊断已上传 CV，不修改你的原 CV；既有 LM PDF 布局保留。需要独立材料版本与事实审核链后再扩展。 |
| 自动联网研究的深度面试包、多轮模拟面试、能力提升学习计划 | 本轮提供有证据的准备资料与问题框架，尚未接入专用模型任务和模拟会话。 |
| Notion 单向同步 | 未配置外部目标；不创建第二个必须维护的申请真源。 |
| 自带薪资样本的统计基准工具 | 当前支持薪资偏好，但没有导入可靠薪资样本，不生成伪分位数。 |
| Apply-Pilot 的 Brave/Mojeek、Adzuna/Jooble/Careerjet/France Travail 密钥 API、JobTech 与 freehire | 本项目有搜索和法国公开页能力，但本轮没有冒充已接这些额外接口；新增接口应按法国实习实际覆盖效果再决定。 |
| Claude/Codex/DeepSeek 等整套命令行启动器、career-ops 包装入口 | 不引入第二套 harness。现有专用 Chrome ChatGPT 工作流保留。 |
| 原版 DOCX 段落模板编辑、SQLite 外部账本导入 | 本轮支持 5 种账本格式；现有 PDF/DOCX CV 上传保留，没有新增模板替换或任意外部数据库挂载。 |
| 自动作跨站账号授权、自动发送跟进邮件 | 本轮邮件仅只读；“我已发送跟进”是记录已发生的事实，不会冒充已经发信。 |

## 使用与验证边界

1. 打开**申请队列**，找到**招聘反馈与下一步**。
2. 若已在**个人档案与账号**配置 Gmail，点**读取 Gmail 招聘反馈**；查看企业、岗位、日期、发件人、主题与证据，勾选后确认。无需连接邮箱也能继续手动记录结果。
3. **需要跟进**只显示真实投递后的到期申请。先自己联系，再点**我已发送跟进**记入历史。
4. **准备面试／检查简历**选择申请即可看 CV 比较、岗位关键词覆盖和面试准备线索。
5. 账本导入始终先预览。已投/被拒/面试等导入记录必须有投递日期；重复记录不会覆盖。无原网址的旧记录只留档，使用不可点击的内部记录标识，不伪造岗位链接，也不能直接进入准备流程。

测试采用合成候选人、临时数据库、假 Gmail 响应和 ATS 样本，不读取用户真实邮箱、不提交真实申请。12 类 ATS 的样本测试证明解析与路由可用，**不证明每个公司的在线接口都可访问**。SuccessFactors 依租户/地区变化，Phenom 的自定义域需明确配置；达到分页上限会报告 capped/partial，不能说已抓全。Gmail 规则可能漏检复杂措辞；冲突/模糊情况要求人工处理。

# 读取结果有疑点时的排查流程

先分清接收企业、招聘服务商、学校活动和具体岗位。域名、标题、Logo 只是线索，不相互替代。优先记录 hiringOrganization、雇主元数据或页面明确的接收企业字段，保留出处与原文。

## REA 的用途

用户指定 [morluto/rea](https://github.com/morluto/rea)。阅读其 [CDP 网站观察说明](https://github.com/morluto/rea/blob/main/docs/browser-observation.md) 后，使用 `rea-agents@6.7.0` CLI 的 `inspect-web-page` 对公共页面做被动观察。它用于调查 DOM、脚本和接口证据，不是职位搜索引擎，也不代替官网业务资料检索。

项目提供可选维护命令：

```powershell
.venv\Scripts\python.exe -m scripts.inspect_qr_source 'https://cv.inmind.fr/saint-gobain/27257?skipWelcome=1' --sources
```

需要现有 Node.js/npm 和平台专用 Chrome；第一次 npx 会缓存固定版本工具。命令创建自己的页面上下文，结束后仅关闭该上下文，不关闭用户标签页、不配置全局 MCP、不提交表单。检查公开网络目标。结果保存在当前候选人的忽略目录 `diagnostics/rea/`。诊断可能包含页面内临时参数或脚本内容，不提交 Git，也不自动发送给模型。默认不采集脚本源码，确有需要时才加 `--sources`。

2026-10-21 实际检查 Saint-Gobain Inmind 入口成功，REA 返回约 5.9 MB 本地证据，包含 `companyName` 字段。没有上传 CV 或发出申请。诊断工具只证明观察到的内容，不保证站点覆盖完整或提交成功。

## 本次落实的适配器

Inmind 页面的 `inmind.companyName` 明确标识接收企业；`inmind.cvInmind=true` 标识通用 CV 收集流程。按该站点契约读取 JSON 字面值，不执行任意 JavaScript。`eventName` 是活动，`Inmind`/`Djigg` 是服务商，均不当作雇主。公司业务查询优先使用接收企业隐私声明明确给出的企业官网。

官网可读时，将业务文本与实际 CV 内容比较，单独标明“企业业务匹配”，不创建虚构职位或任务。官网无法读取时，专用 Chrome 中的 ChatGPT 可查询该企业官网；其业务结论作为未独立核验建议展示来源，CV 原文引用仍检查确实存在。匹配不明确时保留综合 CV 建议，用户可手动指定；手动选定的 CV 不被自动路由覆盖。

通用 CV 收集入口只发 CV，沿用现有 `requires_letter` 的 general 规则。点击“仅投递简历”时，如尚未查询企业业务且未手选 CV，先执行企业查询和自动选择，再通过原有平台投递引擎执行；若网站要求额外问题、登录或隐私决定，原有接管机制继续生效。是否成功仍以网站回执为准。

## Google Forms 与 SuccessFactors（2026-10-21）

Google Forms 优先从表单主标题和介绍中“CV 提交给谁/由谁审核”的明确句子提取接收单位。Google Logo、页脚、OpenGraph 站点名只表示托管方。例如“Récupération de CV au CEA”识别为 CEA 的通用 CV 库，不生成虚构岗位或动机信；泛化到其他明确命名的收件单位，没有硬编码 CEA。旧预览在读取或确认材料时也会用已保存的原文修正。与托管无关的真正 Google 岗位不会被全局排除。

SuccessFactors 托管页同样排除 SAP/SuccessFactors 服务商页脚，读取雇主招聘标题、雇主 Logo 文本或招聘结构化数据；“Alstom Careers Home”显示为 Alstom。会话参数本身不是企业依据。用户给出的仅含 `_s.crb` 的链接在普通读取和专用 Chrome 中均显示处理失败/检查网址的错误页，故保留链接异常状态，不声称已解析出 Alstom 或可以直接投递。独立验证 [Alstom 官方招聘入口](https://jobsearch.alstom.com/)可读，其雇主品牌可以识别。不会擅自将一个失效申请链接换成招聘首页并声称目标岗位相同。

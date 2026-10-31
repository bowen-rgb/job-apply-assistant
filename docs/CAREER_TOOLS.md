# 完整求职工具 / Outils de candidature

入口：**总菜单 → 材料与助手**（业务页顶部也有直接入口）。沿用当前候选人、同一个后端、同一份岗位与申请数据库。不会打开另一套上游应用。

## 最短使用示例

1. 选择要使用的个人档案，确认已有简历。
2. 打开“材料与助手”，选择“研究企业与原始来源”，选一个岗位，点“开始这项任务”。结果和任务进度显示在下面。
3. 改选“定制该岗位简历”。下载生成的 PDF，查看完整结果中的原文依据、审稿和版面检查。核对后点“已核对：将这份简历用于该岗位”。原简历不会被覆盖。
4. 回原申请队列继续准备／投递。新的工具不会把分析完成当成网站投递成功。

Exemple : choisissez votre profil, puis une offre et une tâche. Téléchargez et vérifiez le CV proposé avant de cliquer sur « Vérifié : utiliser ce CV pour cette offre ». Le CV original et la confirmation d’envoi restent distincts.

## 页面分工

- 岗位：启动扫描、筛选岗位、核验并确认。
- 申请队列：准备前自动 AI 复核、当前投递进度和异常接管。疑点最多复核两轮，明确通过后继续；原有手工批量复核保留为补充工具。
- 反馈与跟进：真实拒信、面试、录用意向、未回复的跟进与账本导入导出。
- 材料与助手：准备申请、材料与简历、来源与连接、数据与检查四个分类；切换不会清空正在填写的表单。

“简单模式”已移除。新手分步练习仍在“从这里开始”，不会再改变其他页面的功能可见性。

“未回复，已结束跟进”与“明确被拒”独立。前者必须人工确认并记录原因，不按天数自动判断；两者均停止跟进提醒，保留申请历史。旧账本的 no_response / no response / sans réponse / 未回复 可正确导入。

## 功能与操作

| 要做什么 | 怎么使用 |
| --- | --- |
| 批量比较岗位 | 选择“批量评分与筛选”，勾选最多 100 个岗位。结果按评分维度计算；未设置维度时按复核置信度排序，不冒充个性化匹配分。勾选结果后才写回复核；人工确认仍保留。 |
| 导入项目、证书、历史资料 | “材料与简历”可多选 PDF、DOCX、TXT、Markdown、JSON、CSV、TSV、XLSX；随后运行“从材料中提取个人事实”。勾选有原文依据的事实才加入当前档案。 |
| 发现新的求职方向 | 填“我喜欢怎样的工作”，运行“扩展求职方向与搜索计划”。选择采用的岗位方向／查询词，会进入下一次平台扫描。学习目标、测评和偏好不变成已掌握技能。 |
| 从真实结果总结经验 | 运行“从真实投递结果总结经验”；只有真实记录的拒绝、撤回、录用、入职／婉拒进入分析。原因不明就保持不明，选择采用的经验只影响当前候选人。 |
| 准备面试／模拟面试 | 选择岗位和技术／HR／终面环节。查看公司原始来源、提问和基于真实 CV 的 STAR 线索；输入回答可继续模拟，最多 30 轮。 |
| 分析技能缺口 | 运行学习计划；缺口必须引用岗位原文。计划不会自动加入技能库存。 |
| 查公开招聘来源 | “来源与连接”中启用来源、填写必要密钥、测试后用原“启动扫描”按钮。测试返回数量和失败原因；没有密钥显示待配置。 |
| 查 LinkedIn 岗位与帖子 | 选择“搜索 LinkedIn 岗位与帖子”，最多三条查询。点“打开专用 Chrome 的 LinkedIn 登录页”完成首次登录。只在新建的搜索页采集，不刷新你的登录页。结果经模型筛选、人工选择后加入待核验岗位。帖子不等于已确认空缺。 |
| 加新招聘网站 | 选择“分析新的公开招聘来源”，填真正的岗位列表页。保存提案后，在来源设置中测试真实查询；读到岗位才可启用。适用于公开 HTML，不把登录墙误当列表。 |
| 自定义文档 | 上传 DOCX／TeX／Typst／PDF／ZIP。DOCX 按段落编辑并生成副本；其余非正文 ZIP 内容保持原样。TeX／Typst 先测试编译，然后在任务中选择模板。PDF 是固定文件，不冒充自动改写模板。 |
| 检查写作 | 粘贴文本检查套话、禁写技能、分号和冗长句。仅为写作诊断；原 LM01–LM12 事实与动机审稿继续有效，API 模型也走同一条规则链。 |
| 薪资基准 | 导入自己的可靠样本。每条需 salary、currency、period、basis（税前／税后等）；company、role、city、source 可筛选。三条以上同口径样本才给分位数，不混合币种／周期／口径。也兼容上游 company index JSON，指数不冒充工资。 |
| 跟进邮件 | 原到期提醒保留。生成跟进草稿后填写真实收件人、核对正文。可先写入 Gmail 草稿；另勾选发送确认才会发出。网络结果不明会锁住重试，先去 Gmail 查证，避免重复发信。 |
| 旧记录／批量记录 | 多文件或文件夹导入，支持 SQLite、CSV、TSV、JSON、Markdown、XLSX。先预览，后追加；不覆盖已有记录。没有职位 URL 的历史记录只能留档。 |
| 带走数据 | 原核验 HTML／Excel 导出继续保留；跟踪记录可导出 JSON、CSV、XLSX、Markdown 或带筛选的独立 HTML 快照。 |
| 归档／重置 | 归档任务保存岗位、历史、所选 CV 和动机信。重置必须先预览并输入 RESET，先生成含文件和数据库 SQL 的 ZIP 备份；保留账号与凭据。不要把备份公开上传。 |

## 模型、账号和编译器

- 默认继续使用平台专用 Chrome 的 ChatGPT。可切换兼容接口（包括 DeepSeek 等）、Anthropic、Ollama、Claude CLI、Codex CLI、OpenCode CLI。模型接收当前任务需要的资料；本地 agent 在独立任务目录中运行，禁用工具或限制只读，不直接改原材料。
- API 密钥加密存储，不进入档案导出；本地 CLI 必须已安装并自行登录。Ollama 需要本机服务及已下载模型。检测不到就显示原因，不声称已连接。
- Gmail 默认仍只读。**启用 Gmail 撰写功能 → 重新连接 Gmail → 授予 gmail.compose** 后才能建草稿／发送。原只读连接不自动升级授权。Google OAuth 配置仍在“个人档案与账号”。
- Notion 填 integration token 与 database/data-source ID，先检查连接，再勾选写入确认。使用 `2026-03-11` API；多数据源数据库要指定 data-source ID。只是原申请账本的单向投影，以稳定候选人／岗位 ID 去重。
- LaTeX／Typst 编译器是可选本地工具。缺失、编译失败、超过页数或缺失 PDF 文本时任务失败，不发布可采用的简历。Poppler 存在时使用移植的高级版面检查，否则保留 pypdf 文本、字号、边界和页数检查，并明确高级检查不可用。

重置按预览列出的个人资料、岗位和材料副本执行；账号、工具任务历史和归档会保留。模板包含的字体与其他资源一起备份后再删除，原始上传文件不受影响。

### 源码模板 ZIP

TeX／Typst 主文件用 `[NAME]`、`[CONTACT]`、`[BODY]`。相关样式、字体可一起放入 ZIP。定制简历必须包含 BODY 并在编译后的 PDF 中找到生成的正文。

其他文档工具可在 ZIP 中加入 `template.json`；只支持明确的文档编译器，不执行 shell 命令或安装脚本：

```json
{
  "entrypoint": "main.md",
  "command": ["pandoc", "{source}", "-o", "{output}"],
  "instructions": "Preserve the template typography and section hierarchy.",
  "max_pages": 2
}
```

支持 pandoc、tectonic、quarto、wkhtmltopdf；需本机原生可执行文件。字体与编译依赖自行安装，测试不通过的模板不能在简历任务中选择。

## 命令行（与界面同一数据）

在项目目录运行 `.venv\Scripts\python.exe -m app.cli --help`；安装包的 runtime 也包含 `app.cli`。设置 `JAA_WORKSPACE_HOME` 指向应用当前数据根目录即可共用记录；`--candidate` 可指定现有档案 ID。

```text
python -m app.cli doctor
python -m app.cli scan --preview
python -m app.cli scan --source adzuna --source francetravail_api
python -m app.cli task interview --job 123 --backend chatgpt
python -m app.cli task-status 1
python -m app.cli eval prompt 123
python -m app.cli eval score 123 --answer model-answer.json
python -m app.cli eval pipeline 123 124 --backend compatible
python -m app.cli accept rank 1 --indexes 0 1
python -m app.cli import existing-records --write
python -m app.cli export applications.md --format md
python -m app.cli linkedin scan --query "stage simulation" --only all
python -m app.cli docx list template.docx
python -m app.cli archive 123
python -m app.cli reset documents
```

`task` 的参数可由 `--params params.json` 提供；`--run` 原地等待任务结束。模板、薪资、关键词、写作检查、阶段、笔记、跟进、批量追加也有命令。兼容上游／career-ops 的账本数据格式，通过 Markdown／TSV 导入导出，不另建强制维护的第二套 harness。

## 验证范围

测试使用合成候选人、临时数据库、固定来源样本和假模型／Gmail／Notion 返回；不实际发送申请或邮件。在线网站可能变化、限流或要求登录；来源检测结果以你本机点击测试时为准。模型审稿和原文引文检查可以减少错误，不能证明每一句推断绝对正确。

概览的“被拒”卡片可直接打开拒绝记录。已投递等待、有回复／面试、待跟进、待决定与被拒由同一份真实申请记录计算；拒绝不包含准备失败、不匹配或未回复。完整整合状态与边界见 [能力状态](third-party/CAPABILITY_STATUS.md)。

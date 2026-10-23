# 法国工程毕业实习：新增来源与现有项目核查

核查日期：2026-10-23。本轮为调研和公开页面观察，没有升级生产依赖、开启额外扫描或发送申请。

## 结论与接入顺序

| 优先级 | 来源 | 现状与建议 |
| --- | --- | --- |
| P0 | JobTeaser 公开岗位 | 当前 PFE 搜索计划包含站点查询，但没有独立来源和直采适配器。公开列表能显示岗位、企业、地点、合同和时长，适合增加分页发现与详情核验。公开列表不等于学校专属岗位全覆盖。 |
| P0 | 1jeune1solution 的大学生实习 | 政府产品已有公开列表及领域、地区、时长筛选；作为补充聚合入口，保留原始来源和申请链接，避免把转载算成多个岗位。不要与中学生观察实习混淆。 |
| P0 | HelloWork | 项目有来源名和 JobSpy 配置，但本机 python-jobspy 1.1.82 的 Site 枚举没有 hellowork。需先在隔离环境验证新版依赖及实习筛选，才能声称直采接通。 |
| P1 | Apec 实习专区 | 官方存在工程机械和 PFE 实习搜索页；适合增加专门的实习发现入口，再读取详情中的地区、时间、资格。不能把全法国结果都列为个人匹配。 |
| P1 | Welcome to the Jungle | 已有来源注册，不能作为新增来源重复计数；应提升其公开详情提取和去重质量。 |
| P2 | France Travail 官方 API | 有正式岗位搜索及详情接口，支持职业、地域、合同等筛选；按其申请访问、认证及数据使用要求接入。对于毕业实习的增益需先实测，不假定岗位类型覆盖完整。 |

## 最适合参考的项目

1. [DGEFP-1j1S/1j1s-front](https://github.com/DGEFP-1j1S/1j1s-front)，MIT。虽然 GitHub 星数不高，但对应实际部署的政府产品，比个人爬虫示例更贴合法国实习。
   - 阅读了 `src/server/stages/domain/stages.ts`：明确区分雇主、来源、申请链接，记录开始日期区间、时长区间及地区。
   - 阅读了 `src/server/stages/repository/sourceDesDonneesStage.ts`：来源枚举包括 JobTeaser、HelloWork、Stage.fr、Welcome to the Jungle、Jobijoba 等。
   - 阅读了 `strapiStages.repository.ts`：数据来自自己的 CMS 服务。开源前端及字段结构不代表合作数据源和后台凭据可直接复用。
   - 借鉴字段模型、筛选交互、来源追溯及返回原始申请入口；保留本项目原生 HTML/JS/CSS 和 Python 后端。
2. [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy)，MIT，核查时约 4,544 stars。上游 `pyproject.toml` 为 1.4.1，仓库有 HelloWork 模块；本机版本为 1.1.82，不可把上游能力当作本机能力。升级涉及 pandas、curl_cffi 等依赖，先验证后部署。
3. [hiratinspace/interninbox](https://github.com/hiratinspace/interninbox)，MIT。适合参考通用 ATS 适配器、发现记录和增量扫描；目前规模小，不标成成熟成品，也不是法国 JobTeaser 抓取器。
4. [lduqueno/dev_jobs_scrapper](https://github.com/lduqueno/dev_jobs_scrapper)：本次检索找到的 JobTeaser 示例之一，约 1 star，未发现明确许可证。读取的代码固定合同为 CDD/CDI、依赖旧 DOM、直接写死地点为 Paris；不能用于可靠的 PFE 匹配，也不直接复制源码。

GitHub 项目的数量和星数只用于核查维护情况，不单独作为成熟度结论。

## REA 实际观察

使用现有 `scripts.inspect_qr_source` 和固定的 `rea-agents@6.7.0`，在专用 Chrome 的独立上下文中被动观察：

- `https://www.jobteaser.com/fr/job-offers?locale=fr`：页面可加载，观察到 1,476 个 DOM 节点。
- `https://www.1jeune1solution.gouv.fr/stages`：页面可加载，观察到 1,761 个 DOM 节点。

原始证据仅保存在当前档案忽略目录 `diagnostics/rea/`，不提交 Git。两个观察均标记 `attach_limited` 和 `policy_filtered`：REA 在加载后附着，不能重建之前全部网络请求；默认未保留 Cookie、存储值、响应正文和脚本源码。这些结果证明此次页面观察成功，不证明已经实现完整采集、登录或投递。

下一步应先验证有限分页的公开岗位发现、原始申请链接、企业名称、时间/方向/地区字段，以及跨 JobTeaser、1jeune1solution、HelloWork 的重复合并，再进入实际扫描。学校专属 Career Center 沿用用户在专用 Chrome 的登录；不通过刷新、反复导航或尝试公开搜索来假装覆盖校内岗位。

## 原始依据

- [JobTeaser 公开岗位](https://www.jobteaser.com/fr/job-offers)
- [JobTeaser 学校渠道介绍](https://www.jobteaser.com/fr)
- [1jeune1solution 实习列表](https://www.1jeune1solution.gouv.fr/stages)
- [法国国民议会答复：实习合作来源](https://questions.assemblee-nationale.fr/q17/17-1509QE.htm)
- [Apec 工程机械实习](https://www.apec.fr/candidat/recherche-stage.html/stage?motsCles=Ing%C3%A9nieur+M%C3%A9canique+-+Stage)
- [France Travail 官方 API 目录](https://www.data.gouv.fr/dataservices/api-offres-demploi)
- [JobSpy 当前依赖和版本](https://github.com/speedyapply/JobSpy/blob/main/pyproject.toml)

## 已实施与验证（2026-10-23）

- 新增 JobTeaser、1jeune1solution、Apec 独立来源；HelloWork、Welcome to the Jungle、France Travail 增加有限分页公开列表发现，六个平台均保留预算内的定向搜索。启用来源后使用原有“扫描招聘网站”按钮。
- JobTeaser 使用实测有效的 `q`、`contract=internship` 和分页参数，避免使用被网站忽略的 `query`。1jeune1solution 从渲染页面的岗位数据读取雇主、地点、开始日期区间、时长、原始来源和申请链接；已知平台的原始详情链接用于跨站合并。
- JobSpy 固定升级至 1.4.1，启动时检查实际支持的平台。新版包含 HelloWork，但不把安装成功当作每次查询必定有结果。
- PFE 地区、时间和合同类型仍在详情核验后匹配；信息不明须复核，不强迫搜索结果包含开始月份或六个月。已明确处于法国其他地区的岗位不列为法兰西岛匹配，alternance 不冒充毕业实习。
- 联网小样本验证：JobTeaser、1jeune1solution、France Travail 公开列表返回详情链接；Apec 返回验证拦截；Welcome to the Jungle 和 HelloWork 此次公开页未给出可解析列表，明确记录失败后保留搜索补充。搜索引擎也可能拦截或返回空结果，不能保证后备路径始终成功。
- 动态读取使用专用 Chrome 的独立上下文，不刷新用户正在登录的标签页。扫描和验证不会提交申请。
- France Travail 当前接入公开页及搜索，尚未接入需申请授权的官方 API；学校专属 Career Center 也尚未实现自动采集。界面和文档不将这两项标成已连通。
- 没有直接复制外部项目源码；借鉴政府项目的雇主、来源和原始申请链接分离模型，保留现有架构。

桌面验证补充：来源能力检查仅解析已安装 JobSpy 的 Site 枚举源码，不在 HTTP 工作线程导入 JobSpy/pandas/numpy；Windows 实机发现后者会在并发线程初始化时卡住。实际采集仍在独立进程，补充防止网页后台加载这些原生依赖的回归测试。桌面端和网页端已验证共用后台，扫描和队列批量复核入口可见。

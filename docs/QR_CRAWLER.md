# 二维码招聘入口：抓取、解释与筛选

二维码投递 → 选择一张卡片 → **抓取官网岗位**。系统读取招聘入口、岗位列表、可识别的分页及岗位详情，在当前窗口显示结果。用关键词、地点、专业方向、最早/最晚开始月份筛选，再点“选择这个岗位”。选择仅更新当前草稿，仍需确认材料和发送。

## 读取顺序

1. 发现 Greenhouse、Lever、Ashby、SmartRecruiters 招聘入口时，优先用公开岗位接口；SmartRecruiters 按 offset 翻页。无需手工维护每家公司的官网列表。
2. 普通公开 HTTP 读取。
3. 读取失败或出现访问挑战时，改用 **Scrapling 0.4.15 Fetcher** 的 Chrome TLS 请求；依赖沿用 `requirements-scrapling.txt`。这是实际调用依赖，不是仅借鉴设计。没有安装时报告依赖缺失，并继续尝试原有 Chrome 备用通道。
4. 静态页面没有内容或仍失败时，通过平台专用 Chrome 读取动态页面。不会改用 Edge，也不会启动 Scrapling 的另一套浏览器。
5. 仍无法确认企业或岗位时，把公开网址和已读取的页面文字交给专用 Chrome 中的 ChatGPT。解释跟随界面语言。招聘入口识别不附带候选人简历。

ChatGPT 的解释和新建议链接是线索，单独标记待核验；企业、具体岗位任务及后续 LM 仍需要原页依据。未确认企业和具体岗位时不会生成冒充针对岗位的信件。

## 进度和真实性

- 每批默认最多 30 页、约 120 秒调度预算（单次 Chrome/ChatGPT 请求可能超过批次预算）；有剩余页面时点“继续抓取”。每批最多 3 次 Chrome 页面读取。
- 当前档案保存已读网址、待抓取页面、岗位和失败原因。停止后保留进度，继续时不重复读取已完成页面。抓取不创建申请、不启动原队列。
- 显示已读页数、发现岗位数、剩余页面和错误网址。遇到拦截、限制或 JavaScript 翻页按钮时显示“部分完成”，不会说整站已抓完或没有岗位。
- HTML 链接分页、公开 ATS 接口、嵌入的已知 ATS 和 JobPosting 结构化数据可处理。任意网站的“加载更多”、登录、验证码、复杂内部搜索接口仍可能需要接管或专用适配器。
- 有界抓取：同站招聘链接及页面实际发现的已知 ATS；最大深度 5、1500 条岗位、2000 个待抓页面。到达限制明确显示部分完成。不能保证任意官网全部收齐。
- 按真实 URL 去重，去掉广告跟踪参数，保留区分岗位的 ref 参数。岗位详情未读、ChatGPT 建议、原页已读分别显示。
- **发布日期不是开始日期。** 缺失开始时间、方向、地点的岗位默认保留并标记待核验；可关闭此选项。筛选不调用投递接口。
- 每个跳转检查公开目标，不读取内网地址；单响应上限 8 MB；Scrapling 每次只请求一次，仍被拦截就回退。没有代理轮换、验证码代答、候选人 cookie 复制或无限重试。

## 开源参考

- [Scrapling](https://github.com/D4Vinci/Scrapling)（BSD-3-Clause）：实际接入其 Fetcher；版本固定在现有依赖 0.4.15，未复制库源码。适合现有 Python 项目，避免再加一个浏览器运行栈。[官方 HTTP API](https://scrapling.readthedocs.io/en/latest/fetching/static/)。
- [Scrapy](https://github.com/scrapy/scrapy)：对比过其调度框架；本模块已有候选人隔离的任务进程和持久队列，未再引入另一套调度器。
- [Crawlee/Apify 请求队列](https://docs.apify.com/storage/request-queue)：参考去重、待处理队列、可恢复抓取机制，未安装或复制 Crawlee。
- [interninbox](https://github.com/hiratinspace/interninbox)：参考公开 ATS 优先发现，是较新的实现参考，不作为成熟度保证。
- [SmartRecruiters 官方 Posting API](https://developers.smartrecruiters.com/docs/endpoints)：公开岗位接口及分页字段。

## 验证边界（2026-10-21）

完整测试集 232 项通过，另有 15 项抓取/备用读取定向检查通过。

回归覆盖：公开接口、分页和断点恢复、长分页链、去重、访问失败重试、私网跳转拒绝、响应限额、读取回退、停止、候选人隔离、筛选/未知字段/非法日期范围、轮询后保留筛选、同卡选岗、桌面/手机无横向溢出及不触发发送。界面截图为模拟岗位：[桌面](assets/angelina/qr-directory-1280.png)、[手机](assets/angelina/qr-directory-375.png)。

真实只读测试：Scrapling 成功读取 example.com；圣戈班招聘入口的普通读取和 Scrapling 均收到 403，专用 Chrome 未提取到岗位列表。专用 Chrome 中的 ChatGPT 能解释该入口并返回 6 条同站建议链接，它们仍是未核验线索。此测试没有把建议写成已验证岗位，也没有发送申请。高星库不等于所有反爬限制都能解决。

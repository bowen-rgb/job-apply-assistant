# 招聘平台登录会话

目的：把招聘平台的登录、保存和再次使用放到“个人档案与账号”，减少每次投递重新登录。

沿用原生 HTML/JavaScript/CSS、现有主题变量和卡片。主信息是平台及会话状态；正常投递优先复用会话，失效后在当前申请页用已保存且开启自动登录的账号完成常见登录表单；手动连接仅作首次设置及异常接管。没有收集密码的新入口，也不会在这里发送申请。已有保存账号的确定性自动登录继续保留。

首批平台：JobTeaser、HelloWork、Apec、Welcome to the Jungle、France Travail，以及已有采集器使用的 Indeed、LinkedIn。1jeune1solution 是聚合入口，说明应使用原始招聘网站账号，而不是制造无意义的登录状态。

- 每个个人档案独立保存，加密文件不进入 Git、不进入档案导出。接口仅返回状态、保存时间和错误，不返回 Cookie、令牌或密码。
- 人工登录窗口由平台工作进程持有。重复打开仅聚焦现有窗口；不刷新、不重载。窗口关闭后不自动重开。
- 用户显式点击保存时，或观察到明确的已登录页面标记后，检查密码、MFA、验证拦截及最终域名。无确定的已登录标记时只能标记“会话已保存，未确认登录成功”，不得显示已连接。验证拦截和登录页不标为成功。
- 保存通过当前页面读取 Cookie 和 localStorage，不使用可能为历史 origin 新建导航的 storage_state。后续申请通过原有 _open_browser 使用已保存的 candidate browser_state。
- 保存后关闭本次独立登录窗口。只允许一次连接一个平台；申请队列运行时不能另开登录会话，避免相互覆盖。
- 清除只作用于当前档案及该平台的本地会话，不注销网站账号，不清除其他平台会话。不自动注册、重置密码、接受隐私条款或绕过验证码。
- 登录状态不是永久保证；网站可让会话过期，后续申请仍须识别登录、验证码和提交结果。

验证：状态分类、未知平台拒绝、接口不泄露秘密、已删除 Cookie 不复活、会话保存不导航；桌面和手机宽度检查操作与布局。


## 内置自动登录流程（2026-10-23）

1. 申请工作进程使用当前个人档案保存的 Cookie/localStorage；没有登录表单时直接继续，不读取账号密码。
2. 遇到标准登录表单时，从本地加密账号库找完全相同的 HTTPS origin。支持同页邮箱密码及“邮箱 → 下一步 → 密码”；提交目标也必须是配置的同一 origin。
3. 每个 origin 的邮箱、密码步骤各最多提交一次。密码错误、MFA、验证码、注册/改密、模糊按钮、未知账号、第三方 SSO 或不明确的登录结果均交给用户；不反复试密码、不重置账号。
4. 登录后继续检查申请页面；如果明确落到账号首页，则返回原岗位。已经打开的申请表不会因此重载。申请邮箱字段不当作登录字段。
5. 可选的手动登录窗口检测到明确成功标记后自动保存并关闭；无明确标记仍保留手动检查保存。状态检查不导航、不刷新，不定时调用 storage_state。
6. “设置自动登录”直接带入平台名称和登录地址。此处只配置凭据，不启动投递，不保证所有 SSO 均可自动化。

### 实际参考与适配

- [Browser Use](https://github.com/browser-use/browser-use)（MIT）：检查了 [storage_state_watchdog.py](https://github.com/browser-use/browser-use/blob/main/browser_use/browser/watchdogs/storage_state_watchdog.py) 的状态加载、保存锁、原子写入及变更持久化，以及 [sensitive_data.py](https://github.com/browser-use/browser-use/blob/main/examples/features/sensitive_data.py) 的按域名限制凭据。借鉴“保存状态优先、凭据兜底”，继续使用本项目 DPAPI 与候选人隔离；没有复制其明文状态文件和日志策略，没有引入云端或完整 Agent 依赖。
- [Stagehand](https://github.com/browserbase/stagehand)（MIT）：检查了 CLI session-manager.ts 的既有会话复用与连接管理；结合 [Browserbase Contexts](https://docs.browserbase.com/platform/browser/core-features/contexts) 的跨运行认证状态复用机制，保留本项目既有专用 Chrome 及任务生命周期。
- [Playwright Python Authentication](https://playwright.dev/python/docs/auth)：按其认证状态复用模式验证“关闭登录 context 后，新 context 仍免再次输入密码”。本项目持久化范围是 Cookie 和 localStorage；未声称完整覆盖 IndexedDB、passkey 或各种 SSO。

本轮为机制参考和本地适配，没有直接复制第三方源码。联网验证了来源仓库和官方文档；真实平台的全自动登录仍取决于用户保存的账号、网站当前页面及验证要求，不能用模拟测试冒充实际登录成功。

## 邮件验证码与无闪窗读取（2026-10-23）

- 正常流程仍是“首次人工登录 → 本机按个人档案加密保存 → 后续申请优先复用”。网站过期、撤销或多重验证可能要求再次登录；本项目保存 Cookie/localStorage，不声称覆盖所有 IndexedDB、passkey 或第三方 SSO。
- Gmail 是独立可选项：在“个人档案与账号 → 连接 Gmail”完成现有 Desktop OAuth 配置，再开启“允许自动读取当前招聘网站的登录验证码”。开关默认关闭，修改开关不会清除已连接邮箱。
- 当前自动收码支持已保存账号登录后出现的同源单输入框、明确验证按钮。账号邮箱必须等于连接的 Gmail；邮件必须近期、发给同一地址、发件域名属于当前网站，并有相应 DMARC 通过记录。只接受具有登录语义且唯一的六位验证码。独立邮件服务域名、短信、Google/Microsoft MFA、恢复密码、交易或不确定验证码均留给人工处理。不会发送、删除邮件、点击邮件链接或改密码。
- 邮件读取在工作进程中限次等待；验证码不进入接口、日志、ChatGPT 或申请记录。只在加密存储中记录已用邮件 ID，避免重复尝试。OAuth 失效或网络错误保留人工验证页。
- 后台网页读取使用独立隐藏 Chrome；读取完成关闭它，不再让临时窗口在桌面出现又消失。明确接管现有标签时仍连接专用 Chrome，不导航、不关闭借用的 context。隐藏读取不写回会话，避免覆盖人工登录结果。
- 二维码人工登录页加载超时时保留窗口，不重复导航；退出时保存一次会话，而不是在人工登录期间定时读取状态。

维护方法参考 [mattpocock/skills](https://github.com/mattpocock/skills) 中 diagnosing-bugs、tdd、improve-codebase-architecture 的复现、行为回归与模块封装原则。保留原有架构；没有执行第三方安装脚本，没有照搬其整套工作流或引入新框架。

验证范围：模拟邮件收码、认证/收件人/时效过滤、关闭登录窗口后复用、同源登录后验证码单次提交、超时窗口保留、隐藏读取及借用窗口所有权。实际 Gmail 收码须配置用户自己的 OAuth 后验证，模拟测试不代表所有招聘平台已实际登录成功。

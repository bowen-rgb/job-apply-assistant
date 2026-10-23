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

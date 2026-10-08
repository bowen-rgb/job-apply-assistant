# 个人档案、网站账号和 Gmail

## 先替谁投递

侧边栏点 **个人档案与账号**。原来的资料留在原档案里；点 **创建并切换** 可以新增你的档案。新档案从空白开始，再点 **打开我的个人资料** 填信息、上传自己的简历。每个档案分别保存岗位、投递历史、文件、网站密码和浏览器登录状态。任务运行时不能切换，请先停止并等待结束。

## 配置一次，之后用队列

以 Alice 在一个招聘网站的账号为例：

1. 先在招聘网站完成注册，确认邮箱和密码能登录。
2. 在 **个人档案与账号 → 添加网站账号** 填平台名称、该网站的 HTTPS 登录网址、Alice 的邮箱和密码，勾选 **允许自动登录**，点 **保存账号**。Indeed、HelloWork 等不同网站分别显示为账号卡片，保存其中一个不会覆盖另一个。同一网站再次保存会更新该网站的账号。每张卡片都可编辑、删除或开关自动登录；编辑时密码留空会保留原密码，换了用户名则需填写新密码。密码在 Windows 当前用户下加密，接口不会返回密码。
3. 勾选 **加入后自动开始处理队列**。如果希望系统发送，另勾选 **表单填写完整时自动发送申请**，点 **保存设置**。默认关闭自动发送。
4. 回到新手引导，选岗位。AI 复核过的绿色和橙色岗位都要由本人先确认。之后点 **自动投递这个岗位**，或在岗位卡片点 **加入队列**。
5. 队列显示当前岗位和步骤：登录、准备材料、填表、发送。只有看到招聘网站的成功文字才记为已投递。

队列已经暂停时，新增岗位不会自行恢复运行。先处理显示的缺项或核实发送结果，再用队列的准备按钮继续。

例如网站要求手机验证码：系统暂停并显示原因。你接管页面，完成验证；若手动发送成功，回到系统点 **已投递**。关闭了页面可重新打开岗位，但未发送的旧输入不能保证恢复。

发送超时或没有成功文字时，系统停下，不自动重发。即使重启或重新排队，已经记录“发送结果不确定”的申请仍要求核实。没有账号、密码错误、注册、找回密码、隐私协议、验证码、MFA、无法识别的表单都可能需要接管。不能保证所有招聘网站都能一键完成。

自动登录只在已配置的 HTTPS 网站来源上执行。登录表单将密码发往其他来源、多个密码框或按钮不明确时会停下。常见可选 Cookie 弹窗可以拒绝；不会自动替人接受不明确的条款。

## Gmail：没有 Google 配置也能用队列

点 **Gmail 配置指引** 查看本地逐步说明。目前提供 Google OAuth 配置、授权连接、显示真实邮箱和断开本地连接。**尚未自动读取验证码或执行找回密码**。

使用自己的 Google Cloud 项目，启用 Gmail API，配置同意屏幕和测试用户，创建 **Desktop app** 类型客户端。把 Client ID 和 Client secret 填在本机页面，保存后点连接，再打开显示的授权链接。使用 `start.bat` 的 `http://127.0.0.1:8765`；授权回调固定为 `http://127.0.0.1:8765/api/gmail/callback`。

只请求 `gmail.readonly`。测试模式的授权可能七天过期，需要重新授权。断开本地连接只删除本地令牌；撤销 Google 授权需要在 Google 账号的第三方连接页操作。密钥、令牌和网站会话保存在 Git 忽略的 `data/` 下并使用 Windows DPAPI 加密，不能随意拷贝给其他 Windows 用户使用。

## Profiles and accounts / Profils et comptes

Choose **Profiles & accounts / Profils & comptes** in the sidebar. Create a separate profile, fill its details and upload its own CV. Stop running tasks before switching. Each profile owns its jobs, history, documents, credentials and recruiter sessions.

Save existing website accounts using their HTTPS login URL. Enable automatic queue start and, separately, automatic submission if wanted. Both are off initially. The beginner journey then offers **Apply automatically / Postuler automatiquement**. AI-reviewed green and orange jobs still require your personal confirmation. Complete forms with a clearly recognized final button can be submitted; only observed confirmation text marks success. Missing input, consent, CAPTCHA, MFA and uncertain sends pause for intervention. An uncertain send is not automatically repeated, including after restarting.

The Gmail page includes configuration, authorization and verified mailbox display. Verification-code retrieval and password recovery are **not implemented yet**. The local Gmail setup guide is available in French, Chinese and English. It uses your Desktop app OAuth client, PKCE, the port 8765 loopback callback and Gmail read-only scope. Local unlink does not revoke Google's consent.

## References

This implementation uses existing Playwright browser primitives and official native OAuth patterns, without copying a third-party auto-apply project or adding an unrestricted click agent.

- [Playwright authentication and storage state](https://playwright.dev/python/docs/auth)
- [Playwright source project](https://github.com/microsoft/playwright)
- [Google OAuth for desktop applications](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Gmail authorization scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Gmail mailbox identity](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users/getProfile)
- [Windows DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)

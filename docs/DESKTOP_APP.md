# Windows 桌面版

运行 `output/desktop/Job-Apply-Assistant-Setup-1.0.0.exe`，按安装向导选择位置。安装后可从桌面或开始菜单打开 **Job Apply Assistant**。应用文件夹里有卸载程序，也可从 Windows「已安装的应用」卸载。

双击图标会自动启动后台，不用运行批处理。重复打开会回到已有窗口。关闭窗口或菜单「退出并停止后台」会取消任务并结束本应用所属的后台进程；强制结束后台时，Windows 进程作业也会清理其子任务。不会结束其他 Python 程序，不会关闭你正在登录的专用 Chrome。

首次安装默认使用 `%APPDATA%/job-apply-assistant-desktop/workspace` 保存资料。已有项目可从「求职助手 → 使用已有项目资料」选择原项目目录，退出旧版后台后切换。不会将个人资料放入安装包，更新和卸载不会删除资料。菜单可以打开实际使用的资料文件夹和日志。当前版本不做自动更新，不会自动恢复投递任务。

招聘页仍使用平台专用 Google Chrome。Google 登录、验证码等需由本人完成。交给本人操作的标签页按 Chrome target ID 识别，登录跳转后仍复用同一页；标签页消失时停止并提示，不自动重开、刷新或重新提交。

## 构建

在装好项目依赖的 Windows x64 Python 环境中：

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_desktop
cd desktop
npm ci
npm test
npm run dist
```

Electron/NSIS 提供独立窗口、单实例、安装向导、快捷方式和卸载入口；原有 HTML/CSS/JavaScript 页面保持不变。Python 运行环境和已安装依赖随包提供，用户无需安装 Python/Node。依赖自身的许可文件随运行环境保留，`runtime-packages.json` 记录版本清单。`desktop/payload` 和构建输出不入 Git。

安装包目前未签名。项目提供的 Angelina 素材沿用用户授权的本地用途，公开分发前应另行核实素材分发权限。

参考：[Electron 安全说明](https://www.electronjs.org/docs/latest/tutorial/security)、[electron-builder NSIS 安装器](https://www.electron.build/nsis/)。

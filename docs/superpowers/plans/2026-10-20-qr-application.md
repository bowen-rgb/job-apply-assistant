# QR application implementation plan

**Goal:** 从二维码图片进入可跟踪的、当前候选人专用的单次自动申请。

**Architecture:** 候选人数据库保存 QR 请求、识别证据和单次授权；图片本地解码，网页只读检查；复用受管 apply_worker，通过独立请求 ID 绑定简历及材料授权。UI 为菜单中的独立对话框。

**Tech Stack:** FastAPI、SQLite、原生 JS/CSS、Pillow/zxing-cpp、现有 Playwright 和材料检查。

## Constraints

不恢复旧队列，不更改全局自动提交。未知来源如实显示。验证码、隐私条款等保留人工接管。CV/资料变化使授权失效；回执不明不重发。共享代码不包含个人材料。

## Tasks

- [x] 新增 `app/qr_application.py`：解码、页面识别、CV 建议、请求隔离；`tests/test_qr_application.py` 覆盖真实编码图片和错误输入。
- [x] 新增 `app/qr_routes.py`：上传、入口选择、状态、单次启动；数据库加每岗位简历选择；扩展 `browser.py`/`apply_worker.py` 使用本次授权及既有回执。测试候选人隔离、重放和材料变更。
- [x] 新增 `static/qr-application.js`/CSS：上传、结果、方向覆盖、单主操作、进度/停止/接管；六语言。`tests/test_qr_ui.py` 验证交互和 1280/375 截图。
- [x] 核对 LM 起草与复核实际调用参数；模拟端到端测试和全套回归；记录 UI 参考规则及未实测边界，提交并同步。

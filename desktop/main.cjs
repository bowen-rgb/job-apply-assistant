const {app, BrowserWindow, Menu, dialog, shell} = require('electron');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const {randomUUID} = require('node:crypto');
const {internalURL, externalURL, backendPaths, sharedBackend} = require('./policy.cjs');
let win, child, exiting = false, stopped = false, backendReady = false, origin, workspace;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => {if (win) {if (win.isMinimized()) win.restore(); win.show(); win.focus();}});
  app.on('before-quit', event => {
    if (stopped) return;
    event.preventDefault();
    if (!exiting) {exiting = true; shutdown().finally(() => {stopped = true; app.quit();});}
  });
  app.on('window-all-closed', () => app.quit());
  app.whenReady().then(boot).catch(error => {
    if (!exiting) dialog.showErrorBox('无法启动求职助手', `${error.message}\n日志位于：${path.join(app.getPath('userData'), 'logs')}`);
    app.quit();
  });
}

function getWorkspace() {
  const config = path.join(app.getPath('userData'), 'workspace.json');
  if (fs.existsSync(config)) return path.resolve(JSON.parse(fs.readFileSync(config, 'utf8')).path);
  // Developer mode reuses current data. A distributable never embeds candidate files or machine paths.
  return app.isPackaged ? path.join(app.getPath('userData'), 'workspace') : path.resolve(__dirname, '..');
}
async function boot() {
  workspace = getWorkspace(); fs.mkdirSync(workspace, {recursive: true});
  win = new BrowserWindow({width: 1440, height: 940, minWidth: 860, minHeight: 620,
    title: 'Job Apply Assistant', backgroundColor: '#f0f8fa', icon: path.join(__dirname, 'assets/icon.ico'),
    webPreferences: {nodeIntegration: false, contextIsolation: true, sandbox: true, webviewTag: false}});
  win.on('closed', () => {win = null; app.quit();});
  win.webContents.setWindowOpenHandler(({url}) => {if (externalURL(url)) shell.openExternal(url); return {action: 'deny'};});
  win.webContents.on('will-navigate', (event, url) => {
    if (!internalURL(url, origin)) {event.preventDefault(); if (externalURL(url)) shell.openExternal(url);}
  });
  win.webContents.session.setPermissionRequestHandler((_web, _permission, callback) => callback(false));
  await win.loadFile(path.join(__dirname, 'loading.html'));
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    {label: '求职助手', submenu: [
      {label: '打开资料文件夹', click: () => shell.openPath(workspace)},
      {label: '打开运行日志', click: () => shell.openPath(path.join(app.getPath('userData'), 'logs'))},
      {label: '在浏览器打开同一工作台', click: () => {if (backendReady) shell.openExternal(origin);}},
      {label: '使用已有项目资料…', click: chooseWorkspace},
      {type: 'separator'}, {label: '退出并停止后台', click: () => app.quit()}]},
    {label: '编辑', submenu: [{role: 'undo'}, {role: 'redo'}, {type: 'separator'}, {role: 'cut'}, {role: 'copy'}, {role: 'paste'}, {role: 'selectAll'}]},
    {label: '显示', submenu: [{role: 'resetZoom'}, {role: 'zoomIn'}, {role: 'zoomOut'}, {role: 'togglefullscreen'}]},
    {label: '帮助', submenu: [{label: '关于', click: () => dialog.showMessageBox(win, {type: 'info', message: 'Job Apply Assistant', detail: '关闭窗口会停止本应用的后台与任务。招聘网站仍在专用 Chrome 中打开，登录时不会自动刷新。个人资料保留在本机，卸载时不删除。'})}]}
  ]));
  await startBackend();
  if (!exiting && win && !win.isDestroyed()) await win.loadURL(origin);
}
async function startBackend() {
  const paths = backendPaths(app.isPackaged, process.resourcesPath, __dirname);
  if (!fs.existsSync(paths.python)) throw new Error('随应用安装的 Python 运行环境缺失，请重新安装。');
  const instance = randomUUID();
  const port = 8765; origin = `http://127.0.0.1:${port}`;
  let existing;
  try {
    const response = await fetch(`${origin}/api/runtime`, {signal: AbortSignal.timeout(1500)});
    if (response.ok) existing = await response.json();
    else throw new Error('本机 8765 端口被旧版或其他服务占用，请先退出旧后台。');
  } catch (error) {
    if (error.message.includes('8765')) throw error;
    // No listener: this desktop owns the new backend and its lifecycle.
  }
  if (existing) {
    if (!sharedBackend(existing, workspace))
      throw new Error('已有后台使用其他资料目录，请先退出该后台，或选择同一个项目资料目录。');
    backendReady = true; return;
  }
  const logs = path.join(app.getPath('userData'), 'logs'); fs.mkdirSync(logs, {recursive: true});
  const log = fs.createWriteStream(path.join(logs, 'desktop.log'), {flags: 'a'});
  child = spawn(paths.python, ['-m', 'app.desktop_host'], {cwd: paths.root, windowsHide: true,
    stdio: ['pipe', 'pipe', 'pipe'], env: {...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8',
      JAA_WORKSPACE_HOME: workspace, JAA_DESKTOP_PORT: String(port), JAA_DESKTOP_INSTANCE: instance}});
  let spawnError;
  child.on('error', error => {spawnError = error;});
  child.stdout.pipe(log, {end: false}); child.stderr.pipe(log, {end: false});
  child.on('exit', () => {log.end(); if (!exiting && backendReady) {
    dialog.showErrorBox('后台已停止', '后台意外退出，任务已经停止。请重新打开求职助手；不会自动重投申请。'); app.quit();
  }});
  for (let count = 0; count < 120; count++) {
    if (exiting) return;
    if (spawnError) throw spawnError;
    if (child.exitCode !== null) throw new Error('后台启动失败，请查看运行日志。');
    try {
      const response = await fetch(`${origin}/api/desktop/ready`, {signal: AbortSignal.timeout(800)});
      if (response.ok && response.headers.get('x-jaa-desktop-instance') === instance) {backendReady = true; return;}
    } catch {}
    await delay(250);
  }
  throw new Error('后台启动超时，请查看运行日志。');
}
async function shutdown() {
  if (!child || child.exitCode !== null) return;
  child.stdin.on('error', () => {});
  child.stdin.end('shutdown\n');
  for (let i = 0; i < 32 && child.exitCode === null; i++) await delay(250);
  if (child.exitCode === null) {
    // Only the PID we spawned. The host's Windows job reaps all its descendants.
    child.kill();
    for (let i = 0; i < 12 && child.exitCode === null; i++) await delay(100);
  }
}
async function chooseWorkspace() {
  const result = await dialog.showOpenDialog(win, {title: '选择原求职平台文件夹（包含 data）', properties: ['openDirectory']});
  if (result.canceled) return;
  const selected = result.filePaths[0];
  if (!fs.existsSync(path.join(selected, 'data'))) return dialog.showErrorBox('没有找到资料', '请选择包含 data 文件夹的原项目目录。');
  const confirm = await dialog.showMessageBox(win, {type: 'question', buttons: ['切换并重启', '取消'], defaultId: 1,
    message: '停止当前任务并切换资料？', detail: '请先退出旧版平台。原档案和简历将直接保留使用，不会发送任何申请。'});
  if (confirm.response !== 0) return;
  fs.writeFileSync(path.join(app.getPath('userData'), 'workspace.json'), JSON.stringify({path: selected}, null, 2));
  app.relaunch(); app.quit();
}

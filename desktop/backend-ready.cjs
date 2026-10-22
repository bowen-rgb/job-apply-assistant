// Startup may be slower immediately after installation and antivirus inspection.
async function waitForBackend({probe, exited, delay, now = Date.now, timeoutMs = 120000, onSlow = () => {}}) {
  const started = now();
  let announced = false;
  while (now() - started < timeoutMs) {
    if (exited()) throw new Error('后台启动失败，请查看运行日志。');
    if (await probe()) return;
    if (!announced && now() - started >= 15000) {announced = true; onSlow();}
    await delay(250);
  }
  throw new Error('后台启动超过两分钟，请查看运行日志后重试。');
}
module.exports = {waitForBackend};

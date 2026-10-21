const path = require('node:path');
function internalURL(value, origin) {
  try { return new URL(value).origin === origin; } catch { return false; }
}
function externalURL(value) {
  try { const u = new URL(value); return ['https:', 'http:', 'mailto:'].includes(u.protocol) && !u.username && !u.password; }
  catch { return false; }
}
function backendPaths(packaged, resources, source) {
  const root = packaged ? path.join(resources, 'backend') : path.resolve(source, '..');
  return {root, python: packaged ? path.join(root, 'runtime', 'python.exe') : path.join(root, '.venv', 'Scripts', 'python.exe')};
}
module.exports = { internalURL, externalURL, backendPaths };

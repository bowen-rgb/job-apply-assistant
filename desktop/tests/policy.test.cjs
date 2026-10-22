const {test} = require('node:test');
const assert = require('node:assert/strict');
const {internalURL, externalURL, backendPaths, sharedBackend} = require('../policy.cjs');
test('reuse requires application identity and the same local workspace', () => {
  assert.equal(sharedBackend({application:'job-apply-assistant',workspace:'C:/Jobs'},'c:/jobs'),true);
  assert.equal(sharedBackend({application:'job-apply-assistant',workspace:'C:/Other'},'C:/Jobs'),false);
  assert.equal(sharedBackend({application:'other',workspace:'C:/Jobs'},'C:/Jobs'),false);
  assert.equal(sharedBackend({},'C:/Jobs'),false);
});
test('renderer stays on exact owned origin; outside links cannot execute protocols', () => {
  assert.equal(internalURL('http://127.0.0.1:123/jobs','http://127.0.0.1:123'), true);
  for (const url of ['http://127.0.0.1:124', 'https://evil.test', 'javascript:alert(1)', 'file:///C:/secret'])
    assert.equal(internalURL(url,'http://127.0.0.1:123'), false);
  assert.equal(externalURL('https://example.test/jobs'), true);
  for (const url of ['javascript:alert(1)', 'file:///C:/secret', 'https://user:pass@example.test'])
    assert.equal(externalURL(url), false);
});
test('installed backend uses bundled runtime, never developer venv', () => {
  const paths = backendPaths(true, 'resources', 'source');
  assert.ok(paths.python.endsWith('python.exe'));
  assert.equal(paths.python.includes('.venv'), false);
});

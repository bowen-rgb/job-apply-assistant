const {test} = require('node:test');
const assert = require('node:assert/strict');
const {waitForBackend} = require('../backend-ready.cjs');
test('cold startup beyond 30 seconds is accepted and announces waiting once', async () => {
  let time = 0, notices = 0;
  await waitForBackend({now:()=>time, delay:async ms=>{time+=ms;}, exited:()=>false,
    probe:async()=>time>=45000, onSlow:()=>notices++});
  assert.equal(time,45000);assert.equal(notices,1);
});
test('failed process does not wait for the full startup budget', async () => {
  await assert.rejects(waitForBackend({exited:()=>true,probe:async()=>false,delay:async()=>{}}),/后台启动失败/);
});
test('a nonresponsive live process has a bounded two minute deadline', async () => {
  let time = 0;
  await assert.rejects(waitForBackend({now:()=>time, exited:()=>false,probe:async()=>false,delay:async ms=>{time+=ms;}}),/两分钟/);
  assert.equal(time,120000);
});

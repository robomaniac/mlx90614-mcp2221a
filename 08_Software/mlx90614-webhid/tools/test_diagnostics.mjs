// Simulated application checks; never opens a USB device.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const html = fs.readFileSync(new URL('../mlx.html', import.meta.url), 'utf8');
const inline = html.match(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i)[1];
const eventStart = inline.indexOf("    els.connectBtn.addEventListener(");
assert.ok(eventStart > 0, 'Locate the UI wiring before evaluating declarations');
const elements = new Map();
const canvasContext = new Proxy({}, { get: (_, key) => key === 'createLinearGradient'
  ? () => ({ addColorStop() {} }) : key === 'measureText' ? () => ({ width: 40 }) : () => {} });
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    textContent: '', innerHTML: '', style: {}, dataset: {}, width: 900, height: 400,
    clientWidth: 900, clientHeight: 400, scrollHeight: 0,
    classList: { add() {}, remove() {}, toggle() {} },
    setAttribute() {}, getContext: () => canvasContext,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 900, height: 400 }),
  });
  return elements.get(id);
}
const options = [1, 2, 4, 5, 10].map(value => ({ ...element('rate' + value), dataset: { value: String(value) } }));
const context = vm.createContext({
  document: { getElementById: element, querySelectorAll: () => options },
  window: { devicePixelRatio: 1 }, navigator: {}, performance: { now: () => Date.now() },
  setTimeout, clearTimeout, Date, console,
});
vm.runInContext(inline.slice(0, eventStart) + `
globalThis.app = {
  state, crc8, validateMlxWord, softResetAndReconnectDevice,
  sampleSensor, readValidatedMlxWord, pollingLoop, log,
  replaceRead(fn) { readMlxWord = fn; },
  replaceCancel(fn) { cancelI2cTransfer = fn; },
  replaceSleep(fn) { sleep = fn; },
  replaceSample(fn) { sampleSensor = fn; },
};`, context);
const app = context.app;
const valid = { error: false, pecOk: true, celsius: 23.5 };

let resetSends = 0;
app.state.device = { sendReport() { resetSends++; }, sendFeatureReport() { resetSends++; } };
app.state.transport = { kind: 'output-input', sendReportId: 0 };
await assert.rejects(app.softResetAndReconnectDevice(), error => error.code === 'SOFT_RESET_DISABLED');
assert.equal(resetSends, 0, 'Recovery must not send a USB reset');
console.log('PASS USB reset is blocked before any HID send');

app.replaceSleep(async () => {});
app.replaceCancel(async () => {});
let reads = 0;
app.replaceRead(async () => { if (++reads === 1) throw new Error('simulated HID timeout'); return valid; });
await app.readValidatedMlxWord(6, 'Ambient');
assert.equal(reads, 2);
assert.equal(app.state.totalRecoveredReads, 1);
assert.ok(app.state.logLines.some(line => line.includes('Ambient register 0x06 read failed (attempt 1/2): simulated HID timeout')));
console.log('PASS a recovered register read retains the failed attempt');

reads = 0;
app.replaceRead(async () => { reads++; throw new Error('simulated repeated failure'); });
await assert.rejects(app.readValidatedMlxWord(7, 'Object'), /simulated repeated failure/);
assert.equal(reads, 2);
assert.equal(app.state.logLines.filter(line => line.includes('simulated repeated failure')).length, 2);
assert.throws(() => app.validateMlxWord({ ...valid, error: true }, 'Object'), /error flag/);
assert.throws(() => app.validateMlxWord({ ...valid, pecOk: false, pec: 0, expectedPec: 1 }, 'Object'), /PEC mismatch/);
console.log('PASS all failed attempts, sensor flags, and bad PEC remain errors');

app.state.totalSamples = 0; app.state.sampleAttempts = 0; app.state.history = [];
app.replaceRead(async register => { if (register === 7) throw new Error('simulated object failure'); return valid; });
await assert.rejects(app.sampleSensor(), /simulated object failure/);
assert.equal(app.state.sampleAttempts, 1);
assert.equal(app.state.totalSamples, 0);
assert.equal(app.state.history.length, 0);
app.replaceRead(async () => valid);
await app.sampleSensor();
assert.equal(app.state.sampleAttempts, 2);
assert.equal(app.state.totalSamples, 1);
assert.equal(app.state.history.length, 1);
assert.match(element('pointsPill').textContent, /1 successful \/ 2 attempted/);
console.log('PASS partial pairs are not plotted; successful and attempted pairs differ');

app.state.readErrorCount = 0; app.state.consecutiveReadErrors = 0;
app.replaceSample(async () => { app.state.polling = false; throw new Error('simulated poll failure'); });
await app.pollingLoop();
assert.equal(app.state.readErrorCount, 1);
assert.ok(app.state.logLines.some(line => line.includes('simulated poll failure')));
assert.match(element('statusText').textContent, /Waiting for the next successful/);
console.log('PASS a failed poll is logged and does not claim recovery');

for (let i = 0; i < 750; i++) app.log('bounded-log-check ' + i);
assert.equal(app.state.logLines.length, 700);
assert.ok(element('log').textContent.includes('\n'));
assert.ok(!element('log').textContent.includes('\\n'));
console.log('PASS logs retain 700 lines and render actual newlines');

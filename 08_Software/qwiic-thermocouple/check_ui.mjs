import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';

const html=fs.readFileSync(new URL('thermocouple.html',import.meta.url),'utf8');
const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)];
assert.equal(scripts.length,1);
assert.equal([...html.matchAll(/<style\b/g)].length,1);
assert.ok(!/<script\b[^>]*src=|<link\b[^>]*rel=["']stylesheet/i.test(html));
new vm.Script(scripts[0][1]);
const context=vm.createContext({performance,setTimeout,clearTimeout,Uint8Array,console});
vm.runInContext(scripts[0][1].split('class BrowserClient')[0]+'\nglobalThis.api={WebBridge,decodeTemperature,identifyConfig};',context);
const {WebBridge,decodeTemperature,identifyConfig}=context.api;
assert.equal(decodeTemperature([1,0x6A]),22.625);
assert.equal(decodeTemperature([0xFF,0x60]),-10);
assert.throws(()=>decodeTemperature([1,0x6A,0]));
assert.equal(identifyConfig([0x40,0x14],0,0,0x60).conversion_ms,320);
assert.throws(()=>identifyConfig([0x14,0x40],0,0,0x60));
class FakeDevice {
 constructor(replies){this.replies=replies;this.sent=[];this.opened=true;}
 addEventListener(name,listener){this.listener=listener;}
 removeEventListener(){this.listener=null;}
 async sendReport(id,packet){assert.equal(id,0);this.sent.push([...packet]);const reply=this.replies.shift();assert.ok(reply,'Unexpected extra exchange');this.listener({reportId:0,data:new DataView(Uint8Array.from(reply).buffer)});}
 async close(){this.opened=false;}
}
const report=(command,data=[],status=0,count=data.length)=>{const r=Array(64).fill(0);r[0]=command;r[1]=status;r[3]=count;r.splice(4,data.length,...data);return r;};
const device=new FakeDevice([report(0x94),report(0x93),report(0x40,[1,0x6A])]);
const bridge=new WebBridge(device,0x60);
assert.equal(decodeTemperature(await bridge.read(0,2)),22.625);
assert.deepEqual(device.sent.map(r=>r[0]),[0x94,0x93,0x40]);
assert.deepEqual(device.sent[0].slice(0,5),[0x94,1,0,0xC0,0]);
assert.equal(device.sent[1][1],2);
await assert.rejects(bridge.exchange([0x70]),/Unsupported/);
await bridge.close();assert.equal(device.opened,false);
const faulty=new FakeDevice([report(0x94),report(0x93),report(0x40,[],0x41,127)]);
await assert.rejects(new WebBridge(faulty,0x60).read(0,2),error=>error.code==='I2C_DATA');
assert.equal(faulty.sent.length,3);
const stale=new FakeDevice([report(0x10)]),staleBridge=new WebBridge(stale,0x60);
await assert.rejects(staleBridge.exchange([0x94]),error=>error.code==='HID_REPORT'&&error.fatal);
await assert.rejects(staleBridge.exchange([0x94]),error=>error.code==='HID_STATE');
console.log('PASS: self-contained HTML/JS, signed decoding, identity/configuration, register framing, retained I2C errors, stale-report stop, reset guard. No USB accessed.');

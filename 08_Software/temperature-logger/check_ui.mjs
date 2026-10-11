import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';
import {webcrypto} from 'node:crypto';

const html=fs.readFileSync(new URL('logger.html',import.meta.url),'utf8');
const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)];
assert.equal(scripts.length,1);assert.equal([...html.matchAll(/<style\b/g)].length,1);
assert.ok(!/<script\b[^>]*src=|<link\b[^>]*rel=["']stylesheet/i.test(html));
new vm.Script(scripts[0][1]);
const context=vm.createContext({performance,setTimeout,clearTimeout,Uint8Array,DataView,TextEncoder,crypto:webcrypto});
vm.runInContext(scripts[0][1].split('async function operation(')[0]+'\nglobalThis.api={OpenLog,CardBus,WebBridge,alarmStep,validateSettings,requiredPollRate,startRecordingFromControls,recordingResult,decorate,csvLine,temperature,friendlyMessage};',context);
const {OpenLog,CardBus,WebBridge,alarmStep,validateSettings,requiredPollRate,startRecordingFromControls,recordingResult,decorate,csvLine,friendlyMessage}=context.api;
// Both transports report the same identity-read failure in different raw formats.
for(const raw of ['reg=0x20 reply=40 41 25 7f 00 00 00 00','reg=0x20 reply=94 01 25 00 00 00 00 00','Register 0x20: 40 41 25 7f 00 00 00 00']){
 assert.match(friendlyMessage(raw),/^Could not read the thermocouple board’s identity\./);
 assert.ok(!friendlyMessage(raw).includes('reply='));
 assert.ok(!friendlyMessage(raw).includes('SD logger'));
 assert.match(friendlyMessage(raw),/Connection log/);
}
assert.match(friendlyMessage('reg=0x00 reply=40 41 25 7f 00 00 00 00'),/a temperature/);
assert.match(friendlyMessage('reg=0x06 unexpected count=3'),/settings/);
assert.match(friendlyMessage('Bridge is not ready. Status: 10 00 00 00 00 00 00 00'),/Clear bridge error/);
assert.match(friendlyMessage('100 kHz was rejected: 10 01 00 00'),/100 kHz/);
assert.match(friendlyMessage('40 41 50 7f 00 00 00 00','SD_I2C_DATA'),/SD logger/);
assert.match(friendlyMessage('SD final synchronization failed: 40 41 50 7f'),/Keep the card inserted/);
assert.match(friendlyMessage('Unexpected HID reply: 10 01 00 00'),/unexpected reply/);
assert.match(friendlyMessage('40 41 25 7f'),/Device communication failed/);
for(const message of ['No device selected.','Low must be below high.','Unknown failure <img>','Recording stopped. SD synchronized, size verified; file closed.'])assert.equal(friendlyMessage(message),message);
const limits={enabled:true,low:0,high:50,hysteresis:2};
assert.equal(alarmStep('normal',50,limits),'high');assert.equal(alarmStep('high',49,limits),'high');
assert.equal(alarmStep('high',47.9,limits),'normal');assert.equal(alarmStep('high',-1,limits),'low');
assert.equal(alarmStep('low',1,limits),'low');assert.equal(alarmStep('low',2.1,limits),'normal');
assert.equal(alarmStep('normal',NaN,limits),'normal');assert.equal(alarmStep('high',99,{...limits,enabled:false}),'normal');
const cfg={interval_s:.25,probe_name:'=Probe, "A"',board_name:'Board',sd:true,sd_address:42};
validateSettings(cfg,4);assert.throws(()=>validateSettings(cfg,2));assert.throws(()=>validateSettings({...cfg,interval_s:NaN},4));
assert.equal(requiredPollRate(.25),4);assert.equal(requiredPollRate(.4),2.5);assert.equal(requiredPollRate(.5),2);assert.equal(requiredPollRate(86400),1/86400);
const controls={interval:{value:'.25'},intervalUnit:{value:'1'},probeName:{value:'Probe'},boardName:{value:'Board'},sd:{checked:true},sdAddress:{value:'42'},rate:{value:'2'}};
controls.rate.options=[1,2,4].map(value=>({value:String(value)}));controls.rate.append=option=>controls.rate.options.push(option);
context.document={getElementById:id=>controls[id],createElement:()=>({})};context.calls=[];
vm.runInContext("state.rate=2;client={async rate(value){calls.push(['rate',value]);state.rate=value;},async recordingAction(action,cfg){calls.push([action,cfg.interval_s]);}}",context);
await startRecordingFromControls();assert.equal(JSON.stringify(context.calls),'[["rate",4],["start",0.25]]');assert.equal(controls.rate.value,'4');
// Never create a file when the required rate change fails.
vm.runInContext("state.rate=2;calls.length=0;client.rate=async()=>{throw new Error('Rate rejected');}",context);
await assert.rejects(startRecordingFromControls(),/Rate rejected/);assert.equal(context.calls.length,0);
// Validate first, then set the exact shared rate (including slower/custom intervals).
controls.interval.value='.24';await assert.rejects(startRecordingFromControls(),/between/);
controls.interval.value='1';vm.runInContext('state.rate=4;client.rate=async value=>{calls.push(["rate",value]);state.rate=value;}',context);await startRecordingFromControls();assert.equal(JSON.stringify(context.calls),'[["rate",1],["start",1]]');
controls.interval.value='.4';vm.runInContext('calls.length=0',context);await startRecordingFromControls();assert.equal(JSON.stringify(context.calls),'[["rate",2.5],["start",0.4]]');
controls.interval.value='3600';vm.runInContext('calls.length=0',context);await startRecordingFromControls();assert.equal(context.calls[0][1],1/3600);assert.equal(context.calls[1][0],'start');
const closed={phase:'stopped',settings:{sd:true},sd_filename:'T123ABCD.CSV',sd_bytes:1000,count:6,available:true,message:'Recording stopped; CSV retained. SD synchronized and size verified; file closed.'};
assert.equal(recordingResult(closed).title,'SD file closed');assert.equal(recordingResult(closed).kind,'success');
assert.equal(recordingResult({...closed,message:'Recording stopped. SD synchronized, size verified; file closed.'}).kind,'success');
assert.equal(recordingResult({...closed,phase:'recording'}),null); // A stale close sentence cannot confirm an active file.
assert.equal(recordingResult(closed,true).title,'Closing SD file…'); // Waiting must not look completed.
assert.equal(recordingResult({...closed,message:'SD final synchronization failed.'}).kind,'warning');
assert.equal(recordingResult({...closed,phase:'error'}).title,'SD close not confirmed');
assert.equal(recordingResult({...closed,phase:'recording'},false,'Request failed').kind,'warning');
assert.equal(recordingResult({...closed,phase:'recording'},false,'',true).kind,'warning');
assert.equal(recordingResult({...closed,settings:{sd:false},sd_filename:''}).title,'Recording stopped · SD was off');
assert.equal(recordingResult({...closed,settings:{sd:false},sd_filename:'',phase:'recording'},false,'Request failed').title,'Recording stop not confirmed');
const identityFault='reg=0x20 reply=40 41 25 7f 00 00 00 00';
const failedRecording={...closed,phase:'error',message:identityFault};
assert.equal(recordingResult(failedRecording).kind,'warning');
assert.match(recordingResult(failedRecording).detail,/thermocouple board’s identity/);
assert.ok(!recordingResult(failedRecording).detail.includes('reply='));
assert.equal(failedRecording.message,identityFault); // Display copy never replaces fault evidence.
const failedRow=decorate({sequence:2,timestamp_ms:1000,status:'error',error_code:'I2C_DATA',error:identityFault},cfg);
assert.ok(csvLine(failedRow).includes(identityFault));
const row=decorate({sequence:1,timestamp_ms:1000,status:'ok',hot_c:100,cold_c:0},cfg);
assert.equal(row.hot_f,212);assert.equal(row.cold_f,32);assert.equal(row.timestamp_utc,'1970-01-01T00:00:01.000Z');
assert.ok(csvLine(row).includes(`'=Probe, ""A""`));
vm.runInContext("unit='F';",context);assert.equal(context.api.temperature(0),32);

class FakeCard {
 constructor(){this.commands=[];this.files=new Map();this.open=false;this.reply=[7];this.selected='';this.drop=false;}
 async write(address,data){assert.equal(address,42);assert.ok(data.length<=32);this.commands.push([...data]);const reg=data[0],arg=Buffer.from(data.slice(1)).toString();this.reply=[7];
  if(reg===0)this.reply=[0x78];else if(reg===1)this.reply=[1];else if(reg===2)this.reply=[3];else if(reg===3)this.reply=[1];
  else if(reg===6){if(this.files.has(arg))this.reply=[5];else this.files.set(arg,Buffer.alloc(0));}
  else if(reg===11){this.selected=arg;this.open=true;}
  else if(reg===12){assert.ok(this.open);if(!this.drop)this.files.set(this.selected,Buffer.concat([this.files.get(this.selected),Buffer.from(data.slice(1))]));}
  else if(reg===13){this.open=false;const r=Buffer.alloc(4);r.writeInt32BE(this.files.get(arg)?.length??-1);this.reply=[...r];}
  else assert.ok([8,17].includes(reg),'Unsafe command');
 }
 async read(address,n){assert.equal(this.reply.length,n);return this.reply;}
}
const fake=new FakeCard(),card=new OpenLog(fake,42);const filename=await card.start('header\r\n');
assert.match(filename,/^T[A-F0-9]{7}\.CSV$/);await card.write('é'.repeat(40));await card.checkpoint();
assert.equal(card.bytes,88);assert.equal(fake.open,true);await card.finish();assert.equal(fake.open,false);
assert.equal(fake.files.get(filename).toString(),'header\r\n'+'é'.repeat(40));assert.ok(fake.commands.filter(p=>p[0]===12).every(p=>p.length<=32));
await assert.rejects(card.command(15),/No delete/);
class LegacyCard extends FakeCard{constructor(major){super();this.major=major;}async write(address,data){await super.write(address,data);if(data[0]===2)this.reply=[this.major];}}
for(const major of [1,2,4]){const legacy=new LegacyCard(major);await assert.rejects(new OpenLog(legacy,42).start('header\r\n'),e=>e.code==='SD_FIRMWARE');assert.deepEqual(legacy.commands.map(p=>p[0]),[0,1,2,3]);assert.equal(legacy.files.size,0);}
const dropped=new FakeCard(),broken=new OpenLog(dropped,42);await broken.start('h');dropped.drop=true;await broken.write('data');await assert.rejects(broken.checkpoint(),e=>e.code==='SD_SIZE');
const report=(cmd)=>{const r=new Uint8Array(64);r[0]=cmd;return r;};
const clearBridgeError=vm.runInContext('clearBridgeError',context);
for(const ack of [0,0x10,0x11]){
 let dirty=true;const commands=[];
 const recoverable={exchange:async payload=>{commands.push([...payload]);assert.equal(payload[0],16);const r=report(16);r[22]=r[23]=1;if(payload[2]===16){dirty=false;r[2]=ack;}r[8]=dirty?0x25:0;return r;}};
 await clearBridgeError(recoverable);assert.deepEqual(commands,[[16],[16,0,16],[16]]);
}
const stillBusy=[];
await assert.rejects(clearBridgeError({exchange:async payload=>{stillBusy.push([...payload]);const r=report(16);r[22]=r[23]=1;r[8]=0x25;return r;}}),e=>e.code==='RECOVERY_BUSY');
assert.equal(stillBusy.filter(p=>p[2]===16).length,1);
const fallback={...closed,phase:'recording',sd_filename:'',sd_phase:'unavailable',sd_error:'40 41 25 7f',sd_error_code:'SD_I2C_DATA'};
assert.equal(recordingResult(fallback).title,'SD unavailable · PC recording continues');
assert.equal(recordingResult(fallback,true).title,'Stopping recording…');
assert.match(recordingResult(fallback).detail,/No SD file was created/);
assert.equal(recordingResult({...fallback,phase:'idle'}),null);
assert.match(recordingResult({...fallback,phase:'stopped'}).title,/PC CSV retained/);
const bridge={exchange:async payload=>{const r=report(payload[0]);if(payload[0]===0x10)r[20]=64;return r;}};
await assert.rejects(new CardBus(bridge).write(42,[0]),e=>e.code==='SD_I2C_STATE');
const readCommands=[],states=[0x50,0x50,0x55];
const stretched={exchange:async payload=>{readCommands.push(payload[0]);const r=report(payload[0]);if(payload[0]===0x10)r[8]=states.shift();if(payload[0]===0x40){r[2]=0x55;r[3]=1;r[4]=0x17;}return r;}};
assert.deepEqual(Array.from(await new CardBus(stretched).read(42,1)),[0x17]);
assert.deepEqual(readCommands,[0x91,0x10,0x10,0x10,0x40]);
const invalidRead={exchange:async payload=>{const r=report(payload[0]);if(payload[0]===0x10)r[8]=0x55;if(payload[0]===0x40){r[1]=0x41;r[2]=0x50;r[3]=127;}return r;}};
await assert.rejects(new CardBus(invalidRead).read(42,1),e=>e.code==='SD_I2C_DATA');
const readNack={exchange:async payload=>{const r=report(payload[0]);if(payload[0]===0x10)r[8]=0x25;assert.notEqual(payload[0],0x40);return r;}};
await assert.rejects(new CardBus(readNack).read(42,1),e=>e.code==='SD_I2C_STATE');
const noReady={exchange:async(payload,end)=>{if(performance.now()>=end)throw Object.assign(new Error('Deadline exceeded'),{code:'SD_TIMEOUT'});assert.ok([0x91,0x10].includes(payload[0]));const r=report(payload[0]);r[8]=0x50;return r;}};
await assert.rejects(new CardBus(noReady).read(42,1),e=>e.code==='SD_TIMEOUT');
let sends=0;const device={addEventListener(){},removeEventListener(){},sendReport(){sends++;}};
await assert.rejects(new WebBridge(device,96).exchange([0x70]),/Unsupported/);assert.equal(sends,0);
await assert.rejects(new CardBus(bridge).write(1,[0]),/Invalid/);
console.log('PASS: standalone syntax, readable errors for both transports, raw CSV/error evidence retained, alarm hysteresis, units/CSV, interval bounds, one exact sample/record rate before file creation, custom and hourly rates, rate-failure guard, SD UTF-8 chunks, synchronized size/close, stretched-read readiness/timeout, invalid read data, firmware guard before file creation, silent-write failure, address NACK, reset/delete guards. No USB accessed.');

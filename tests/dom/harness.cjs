'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const assert = require('node:assert/strict');
const {JSDOM, VirtualConsole} = require('jsdom');
const root = path.resolve(process.env.GURUMOJI_DOM_SOURCE_ROOT || path.join(__dirname, '../..'));
const html = execFileSync(process.env.GURUMOJI_TEST_PYTHON || 'python3', [path.join(__dirname, 'render_fixture.py'), root], {encoding:'utf8'});
const flush = async () => { for (let i=0;i<8;i++) await new Promise(resolve=>setImmediate(resolve)); };
async function createHarness() {
  const errors=[], requests=[], blocked=[], timers=[];
  const console = new VirtualConsole(); console.on('jsdomError', error=>errors.push(error));
  // No resources option: jsdom never loads script/style/image/frame subresources.
  const dom = new JSDOM(html, {url:'https://gurumoji.invalid/', runScripts:'outside-only', virtualConsole:console});
  const w=dom.window, context=dom.getInternalVMContext();
  const evaluate=source=>new vm.Script(source).runInContext(context);
  w.matchMedia=query=>({matches:false,media:query,addEventListener(){},removeEventListener(){}});
  w.scrollTo=()=>{}; w.HTMLElement.prototype.scrollIntoView=()=>{};
  for(const name of ['load','pause','play']) w.HTMLMediaElement.prototype[name]=()=>name==='play'?Promise.resolve():undefined;
  // Explicit semantic-only dialog shim. No modality/top-layer/focus/keyboard guarantee.
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  w.HTMLDialogElement.prototype.close=function(){if(this.open){this.open=false;this.dispatchEvent(new w.Event('close'));}};
  w.confirm=()=>true; w.alert=()=>{};
  // Deterministic scheduling: boot/poll timers and rAF never fire automatically.
  w.setTimeout=(callback,delay)=>{timers.push({callback,delay});return timers.length;}; w.clearTimeout=()=>{};
  w.setInterval=w.setTimeout; w.clearInterval=()=>{}; w.requestAnimationFrame=w.setTimeout; w.cancelAnimationFrame=()=>{};
  for(const api of ['XMLHttpRequest','WebSocket','EventSource']) w[api]=class {constructor(){blocked.push(api);throw Error(`${api} forbidden in offline DOM harness`);}};
  w.navigator.sendBeacon=()=>{blocked.push('sendBeacon');throw Error('sendBeacon forbidden');};
  const reply=(request,data,status=200)=>{
    assert.equal(request.settled,false,`fixture already answered: ${request.url}`);request.settled=true;
    // Parse fixture JSON in the jsdom realm, never evaluate fixture strings as code.
    w.__responseJSON=JSON.stringify(data); const payload=evaluate('JSON.parse(window.__responseJSON)');delete w.__responseJSON;
    request.resolve({ok:status>=200&&status<300,status,json:async()=>payload,text:async()=>JSON.stringify(payload),headers:new w.Headers()});
  };
  const fail=(request,message='Synthetic transport failure')=>{
    assert.equal(request.settled,false,`fixture already answered: ${request.url}`);request.settled=true;
    request.reject(new w.Error(message));
  };
  w.Headers=class Headers {constructor(values={}){this.values={...values};}set(k,v){this.values[k]=v;}get(k){return this.values[k]||null;}};
  w.fetch=(url,options={})=>new Promise((resolve,reject)=>{
    const request={url:String(url),options,resolve,reject,settled:false};requests.push(request);
    const target=new URL(request.url,w.location.href);
    if(target.origin!==w.location.origin||!target.pathname.startsWith('/api/')){blocked.push(request.url);request.settled=true;reject(Error('Only offline same-origin API fixtures are allowed'));return;}
    const startup={ '/api/training':{event_count:0,ready_count:0}, '/api/jobs/active':{job:null}, '/api/library?keyword=&speaker=&emotion=&group=&sort=updated_desc':{items:[]}, '/api/library?sort=updated_desc':{items:[]}, '/api/library/interview-comparison/runs':{runs:[]}, '/api/config':{ok:true,runtime:{browser_upload:true}}, '/api/custom-vocabulary':{terms:[]}, '/api/speakers':{speakers:[],registry_revision:0}};
    if(Object.hasOwn(startup,request.url))reply(request,startup[request.url]);
  });
  w.sessionStorage.setItem('gurumoji.bootSplashSeen','1');
  for(const element of w.document.querySelectorAll('script[src]')) {
    const url=new URL(element.src);assert.equal(url.origin,'https://gurumoji.invalid');
    assert.match(url.pathname,/^\/static\/[a-z-]+\.js$/);
    new vm.Script(fs.readFileSync(path.join(root,'src/gurumoji',url.pathname),'utf8'),{filename:url.pathname}).runInContext(context);
  }
  await flush();
  return {dom,w,document:w.document,requests,errors,blocked,timers,evaluate,reply,fail,flush,
    fixture(value){w.__fixtureJSON=JSON.stringify(value);evaluate('window.fixture = JSON.parse(window.__fixtureJSON)');delete w.__fixtureJSON;},
    change(element,value){assert(element);element.value=value;element.dispatchEvent(new w.Event('change',{bubbles:true}));},
    click(selector){const element=typeof selector==='string'?w.document.querySelector(selector):selector;assert(element,selector);element.click();},
    close(){try{assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);assert.deepEqual(requests.filter(r=>!r.settled).map(r=>r.url),[], 'Every intercepted request must receive a test-owned fixture');}finally{dom.window.close();}}
  };
}
module.exports={createHarness,flush};

// Original source handler; synthetic DOM/API boundaries only, no browser or HTTP.
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const sourcePath = path.join(root, 'src/gurumoji/static/analysis-content.js');
const text = fs.readFileSync(sourcePath, 'utf8');
const start = text.indexOf('async function openInsightMedia(segment)');
const stop = text.indexOf('function restoreAnalysisEvidencePosition()', start);
if(start < 0 || stop < 0) throw new Error('Handler source boundary missing');
const helper = text.slice(text.indexOf('function analysisEvidenceTimeValid('), text.indexOf('function evidenceDetails('));
const fn = helper + text.slice(start, stop);
async function run(name, saved, current, expectedPlayCalls) {
  const log = { apiRequests: [], plays: [], alerts: [], renderCount: 0 };
  const controls = new Map();
  const document = { querySelector: key => {
    if(!controls.has(key)) controls.set(key, {hidden:true,value:''});
    return controls.get(key);
  }};
  const context = vm.createContext({
    analysisState:{ itemId:'synthetic-A', mode:'automatic', automaticScope:'all', selectedSpeaker:'' },
    analysisRequestSequence:1, analysisEvidenceRequest:0, analysisCatalog:[],
    captureAnalysisContext:()=>({}), isAnalysisContextCurrent:()=>true, analysisEvidenceReturn:null, selectedSegmentId:null,
    window:{scrollY:0}, document, mediaPlayer:{},
    apiFetch:async url => { log.apiRequests.push(url); return {ok:true}; },
    readJsonResponse:async () => ({segments:[current]}),
    renderResult:() => log.renderCount++, renderSegments:()=>{},
    playSegment:id => log.plays.push(id), setAlert:(_element,message,error)=>log.alerts.push({message,error}),
  });
  vm.runInContext(fn,context);
  await context.openInsightMedia(saved);
  return {name,expectedPlayCalls,actualPlayCalls:log.plays.length,contractPassed:log.plays.length===expectedPlayCalls,...log};
}
(async()=>{
  const base={id:'e1', text:'Synthetic quote', speaker:'A'};
  const cases = [
    ['matching_valid', {...base,start:0,end:2}, {...base,start:0,end:2}, 1],
    ['matching_true_zero', {...base,start:0,end:0}, {...base,start:0,end:0}, 1],
    ['null_timestamp', {...base,start:null,end:null,time_unknown:true}, {...base,start:null,end:null,time_unknown:true}, 0],
    ['missing_timestamp', {...base}, {...base}, 0],
    ['negative_timestamp', {...base,start:-4,end:-2}, {...base,start:-4,end:-2}, 0],
    ['invalid_numeric_timestamp', {...base,start:'bad',end:'bad'}, {...base,start:3,end:4}, 0],
    ['time_unknown_with_numeric_placeholder', {...base,start:0,end:0,time_unknown:true}, {...base,start:0,end:0,time_unknown:true}, 0],
    ['changed_text', {...base,start:0,end:2}, {...base,start:0,end:2,text:'Changed'}, 0],
    ['changed_valid_time', {...base,start:0,end:2}, {...base,start:3,end:4}, 0],
  ];
  for (const bad of [null, undefined, '', '0', NaN, Infinity, -1]) {
    cases.push(['saved-invalid-' + String(bad), {...base,start:bad,end:2}, {...base,start:0,end:2}, 0]);
    cases.push(['current-invalid-' + String(bad), {...base,start:0,end:2}, {...base,start:bad,end:2}, 0]);
  }
  cases.push(['reversed', {...base,start:4,end:2}, {...base,start:4,end:2}, 0]);
  cases.push(['current-unknown', {...base,start:0,end:2}, {...base,start:0,end:2,time_unknown:true}, 0]);
  const results=[];
  for(const c of cases) results.push(await run(...c));
  if (results.some(result => !result.contractPassed)) process.exitCode = 1;
  console.log(JSON.stringify({source:'src/gurumoji/static/analysis-content.js',source_sha256:crypto.createHash('sha256').update(text).digest('hex'),scope:'Source handler with synthetic DOM and fetch; not real browser, audio, HTTP or current private data',results},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});

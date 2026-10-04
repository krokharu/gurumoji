// Attribute construction only; never follows a URL or executes fixture content.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../src/gurumoji/static/analysis-storage.js'),'utf8');
function node(tag='div'){return {tag,children:[],dataset:{},_text:'',
 set textContent(value){this._text=String(value??'');this.children=[];},get textContent(){return this._text+this.children.map(n=>n.textContent??'').join(' ');},
 append(...n){this.children.push(...n);},replaceChildren(...n){this.children=n;},setAttribute(){}};}
const history=node(),ctx={URL,analysisState:{itemId:'A',data:{}},analysisSaveInProgress:false,
 document:{querySelectorAll:selector=>selector==='[data-archive-history]'?[history]:[]},formatDate:()=> 'saved',
 analysisElement(tag,cls,text=''){const n=node(tag);n.textContent=text;return n;},contentButton:text=>{const n=node('button');n.textContent=text;return n;}};
vm.createContext(ctx);vm.runInContext(source,ctx);
const valid=['obsidian://open?path=%2Fsynthetic%2Fnote.md','obsidian://open?path=C%3A%5CSynthetic%5Cnote.md','obsidian://open?path=%2Fsynthetic%2F%E4%BC%9A%E8%A9%B1.md'];
for(const value of valid)assert.equal(ctx.savedAnalysisObsidianUri(value),value);
const invalid=['javascript:alert(1)','data:text/html,test','//open?path=x','https://open?path=x','obsidian://new?path=x','obsidian:open?path=x',
 'obsidian://open/?path=x','obsidian://open?file=x','obsidian://open?path=','obsidian://open?path=x&path=y','obsidian://open?path=x&append=yes',
 'obsidian://open?path=x#fragment','obsidian://user@open?path=x','obsidian://open:80?path=x','obsidian://open?path=%ZZ','obsidian://open?path=%FF',
 'obsidian://open?path=%00x','obsidian://open?path=%0Ax','obsidian://open?path=\tx',' obsidian://open?path=x',null,{},0];
for(const value of invalid)assert.equal(ctx.savedAnalysisObsidianUri(value),'',String(value));
for(const value of ['abc','a/../b?x#y','日本語'])assert.equal(ctx.savedAnalysisArtifactUrl(value),`/api/analysis/artifacts/${encodeURIComponent(value)}`);
for(const value of ['',null,{},0,'.','..',' x','x\n','\ud800'])assert.equal(ctx.savedAnalysisArtifactUrl(value),'');
const links=n=>[...(n.tag==='a'?[n]:[]),...n.children.flatMap(links)];
const run={id:'run',status:'completed',kind:'text_analysis',obsidian_uri:'javascript:alert(1)',artifacts:[{id:'abc',name:'safe',url:'data:text/html,test'},{name:'missing',url:'https://unexpected.invalid/'}]};
ctx.analysisStorageState().runs=[run];ctx.refreshAnalysisStorage();
assert(links(history).every(n=>n.href.startsWith('/api/analysis/')));assert(links(history).some(n=>n.href==='/api/analysis/artifacts/abc'));
assert(history.textContent.includes('Obsidianのリンクを確認できません'));assert(history.textContent.includes('ファイルIDを確認できない'));
run.obsidian_uri=valid[0];ctx.refreshAnalysisStorage();assert(links(history).some(n=>n.href===valid[0]));
run.artifacts[0].id='changed';ctx.refreshAnalysisStorage();assert(links(history).some(n=>n.href==='/api/analysis/artifacts/changed'));
run.obsidian_uri='data:text/html,test';ctx.refreshAnalysisStorage();assert(!links(history).some(n=>n.href===valid[0]));
console.log('PASS history URL allowlist, encoded artifact IDs, unavailable states, live history metadata refresh; no navigation');

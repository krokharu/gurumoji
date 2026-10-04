// Diagnostic only: synthetic fixtures, full project scripts, no expected-bug assertions.
const {createHarness}=require('./harness.cjs');
(async()=>{
 const h=await createHarness(),results={};
 const data={id:'A',segments:[{id:'s1',speaker:'A',start:0,end:1,text:'Synthetic'}],speaker_profiles:{A:{display_name:'Before',session_role:'participant',session_role_source:'default'}},speaker_names:{},session_profile:{}};
 h.fixture(data);h.evaluate('renderResult(window.fixture)');
 let row=h.document.querySelector('.conversation-speaker-sheet tbody tr');
 results.unnamedControls=[...row.querySelectorAll('input,select,textarea')].filter(n=>!n.getAttribute('aria-label')&&!n.getAttribute('aria-labelledby')&&!n.labels?.length).map(n=>n.tagName);
 const name=row.querySelector('input[type=text]');name.value='After';name.dispatchEvent(new h.w.Event('input',{bubbles:true}));
 results.nameChange={roleLabel:row.querySelector('.conversation-role-control select').getAttribute('aria-label'),marker:h.evaluate('currentJob.speaker_profiles.A.session_role_source')};
 const globalSelect=row.querySelector('select');globalSelect.focus();globalSelect.dispatchEvent(new h.w.Event('change',{bubbles:true}));results.registryChangeActiveTag=h.document.activeElement.tagName;
 h.fixture({itemId:'A',data:{item:{id:'A'},segments:[]}});h.evaluate('Object.assign(analysisState,window.fixture);document.querySelector("#analysis-card").append(buildAnalysisStorage())');
 const lookup=h.document.querySelector('.analysis-fixed-lookup');lookup.querySelector('input').value='r1';lookup.requestSubmit();
 h.reply(h.requests.at(-1),{run:{id:'r1',item_id:'A',artifacts:[]},integrity:'verified'});await h.flush();
 h.evaluate('showView("library", {force:true})');results.navigation={dialogOpen:h.document.querySelector('.analysis-fixed-dialog').open,route:h.w.location.hash};
 for(const label of ['__proto__','constructor','toString','A']){
  h.fixture({...data,segments:[{id:'s1',speaker:label,start:0,end:1,text:'Synthetic'}],speaker_profiles:{}});
  h.evaluate('currentJob=window.fixture');
  results['metrics_'+label]=h.evaluate('JSON.stringify(speakerMetrics())');
 }
 results.prototype=h.evaluate('JSON.stringify({count:Object.prototype.count,seconds:Object.prototype.seconds,characters:Object.prototype.characters})');
 for(const status of ['constructor','toString','__proto__','completed','not_run']){h.fixture({methods:[{status,title:'Synthetic'}]});results['status_'+status]=h.evaluate('buildFixedAnalysisSummary(window.fixture).textContent');}
 console.log(JSON.stringify(results,null,2));h.close();
})().catch(e=>{console.error(e);process.exitCode=1;});

// 一時アプリで、削除後に残す主要操作を実際のブラウザーから検証する。
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base='http://127.0.0.1:17864';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const outcomes=[];
 try {
  for(const width of [1365,390]){
   const context=await browser.newContext({viewport:{width,height:980}});
   const page=await context.newPage();const errors=[],forbidden=[],failed=[];const steps=[];
   page.on('pageerror',e=>{errors.push(e.message);console.error('JS_ERROR',e.message);});
   page.on('request',r=>{if(/\/(analysis|orchestration|obussql|obsidian)|interview-comparison/.test(r.url()))forbidden.push(r.url());});
   page.on('response',r=>{if(r.status()>=500&&r.url().startsWith(base))failed.push({url:r.url(),status:r.status()});});
   page.on('dialog',d=>d.accept());
   async function nav(id,view){await page.locator(id).click();await page.waitForFunction(v=>document.body.dataset.view===v,view);steps.push(view);}
   async function request(method,url,data){const r=await page.request.fetch(base+url,{method,headers:{'X-Gurumoji-Request':'1'},data});assert(r.ok(),url+' '+r.status()+' '+await r.text());return r.json();}
   await page.goto(base,{waitUntil:'networkidle'});
   await nav('#show-library-button','library');
   const row=await request('POST','/api/library',{source_name:'ブラウザー確認 '+width});
   const segments=Array.from({length:205},(_,i)=>({id:'browser-'+i,start:i,end:i+1,speaker:i%2?'SPEAKER_01':'SPEAKER_00',text:i===204?'末尾検索専用キーワード':'確認発話 '+i}));
   const saved=await request('PUT','/api/library/'+row.id,{revision_count:row.revision_count,segments,speaker_names:{}});
   await page.goto(base+'/#/data/'+row.id,{waitUntil:'networkidle'});
   await page.locator('#segment-page-label').filter({hasText:'1 / 3'}).waitFor();steps.push('205segments');
   await page.locator('#segment-page-next').click();
   await page.locator('#segment-page-label').filter({hasText:'2 / 3'}).waitFor();steps.push('pagination');
   await page.locator('#segment-keyword').fill('末尾検索専用キーワード');
   await page.locator('article.segment').filter({hasText:'末尾検索専用キーワード'}).waitFor();
   assert.equal(await page.locator('article.segment').count(),1);steps.push('worker-search');
   await page.locator('#segment-keyword').fill('');
   await page.waitForFunction(()=>document.querySelectorAll('article.segment').length===100);
   await page.locator('article.segment .segment-edit').first().click();
   await page.locator('textarea[data-segment-field="text"]:visible').first().fill('ブラウザーで編集して保存しました');
   const updated=page.waitForResponse(r=>r.request().method()==='PUT'&&r.url()===base+'/api/library/'+row.id);
   await page.locator('#save-button').click();const editResponse=await updated;assert(editResponse.ok(),await editResponse.text());
   const value=await editResponse.json();assert(value.segments.some(s=>s.text==='ブラウザーで編集して保存しました'));steps.push('edit-save');
   await nav('#show-speakers-button','speakers');
   await page.locator('#add-speaker-button').click();
    await page.locator('[data-speaker-field="display_name"]:visible').first().fill('確認話者 '+width);
    await page.locator('[data-speaker-field="pseudonym"]:visible').first().fill('確認用仮名 '+width);
   if(!(await page.locator('[data-speaker-field="attributes"]:visible').count())){
     await page.locator('.speaker-card-details:visible').first().locator('summary').click();
   }
    await page.locator('[data-speaker-field="attributes"]:visible').first().fill('質問=確認回答');
   const speakerSave=page.waitForResponse(r=>r.request().method()==='PUT'&&r.url()===base+'/api/speakers');
    await page.locator('#save-speakers-button').click();
    const speakerResponse=await speakerSave;assert(speakerResponse.ok());
    assert((await speakerResponse.json()).speakers.some(s=>s.display_name==='確認話者 '+width&&s.pseudonym==='確認用仮名 '+width));steps.push('speaker-save');
   await nav('#prior-folders-button','folders');
   await page.locator('#library-group-name').fill('確認フォルダー '+width);
   const folderSave=page.waitForResponse(r=>r.request().method()==='POST'&&r.url()===base+'/api/library/groups');
   await page.locator('#library-group-create-form button[type=submit]').click();assert((await folderSave).ok());steps.push('folder-save');
   await nav('#prior-catalog-button','catalog');
   await page.locator('#data-tag-name').fill('確認タグ '+width);
   const tagSave=page.waitForResponse(r=>r.request().method()==='POST'&&r.url()===base+'/api/library/tags');
   await page.locator('#data-tag-form button[type=submit]').click();assert((await tagSave).ok());steps.push('tag-save');
   await nav('#prior-presets-button','presets');
   await page.locator('#preset-manager-name').fill('確認プリセット '+width);
   await page.locator('#preset-manager-save').click();
   await page.waitForFunction(w=>document.querySelector('#preset-manager-select').textContent.includes('確認プリセット '+w),width);steps.push('preset-save');
   await page.locator('#open-general-settings').click();
   await page.locator('label:has(input[name=gs-theme][value=teal])').click();
   await page.locator('#general-settings-dialog button[type=submit]').click();steps.push('settings-theme');
   await nav('#prior-internal-button','internal');
   await nav('#show-new-button','new');
   await page.screenshot({path:__dirname+'/extended-public-'+width+'.png',fullPage:true});
   assert.deepEqual(errors,[]);assert.deepEqual(forbidden,[]);assert.deepEqual(failed,[]);
   outcomes.push({width,steps,jsErrors:errors.length,removedApiRequests:forbidden.length,serverErrors:failed.length});
   console.log(JSON.stringify(outcomes.at(-1)));
   await context.close();
  }
  require('node:fs').writeFileSync(__dirname+'/public-extended-browser-results.json',JSON.stringify(outcomes,null,2));
  console.log(JSON.stringify(outcomes));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

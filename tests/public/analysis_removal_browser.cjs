// 一時データの公開版をブラウザーで検証する。実利用者のアプリには接続しない。
const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:1365,height:980}});
 const errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>requests.push(r.url()));
 await page.goto('http://127.0.0.1:17864/',{waitUntil:'networkidle'});
 await page.locator('#show-library-button').click();
 await page.waitForTimeout(500);
 await page.locator('#show-speakers-button').click();
 await page.waitForTimeout(500);
 const created=await page.request.post('http://127.0.0.1:17864/api/library',{headers:{'X-Gurumoji-Request':'1'},data:{source_name:'Browser check'}});
 const item=await created.json();
 await page.goto('http://127.0.0.1:17864/#/data/'+item.id,{waitUntil:'networkidle'});
 await page.waitForTimeout(500);
 console.log(JSON.stringify({errors,forbiddenRequests:requests.filter(u=>/\/analysis|\/orchestration|\/obsidian|interview-comparison/.test(u)),view:await page.locator('body').getAttribute('data-view'),record:await page.locator('#result-card').isVisible()}));
 await page.screenshot({path:__dirname+'/public-removal-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.goto('http://127.0.0.1:17864/',{waitUntil:'networkidle'});
 await page.screenshot({path:__dirname+'/public-removal-mobile.png',fullPage:true});
 console.log(JSON.stringify({allErrors:errors}));
 await browser.close();
 if(errors.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});

"""出荷コードの起動・切替・繰り返しをGIFと静止画へ描画する。"""
import argparse
import json
import math
import time
from io import BytesIO
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser()
parser.add_argument('--source-root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();root=args.source_root.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
source=(root/'src/gurumoji/static/progress-journey.js').read_text(encoding='utf-8').split('let progressJourneyJob =')[0]
css=(root/'src/gurumoji/static/stitch-theme.css').read_text(encoding='utf-8')
markup='''<meta charset="utf-8"><main class="motion-preview"><h1>グルモジ 共通モーション</h1><div class="preview-heading"><h2 id="preview-title">環境の確認</h2><span id="preview-cycle">起動</span></div><div id="preview-motion" class="progress-motion" aria-hidden="true"></div></main>'''
style='''*{box-sizing:border-box}body{margin:0;padding:20px 24px;color:#153c2f;background:#f5faf6;font-family:"Yu Gothic UI",Meiryo,sans-serif}.motion-preview h1{margin:0 0 14px;font-size:19px;letter-spacing:.03em}.preview-heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;gap:12px}.preview-heading h2{margin:0;font-size:25px}.preview-heading span{padding:6px 12px;border-radius:999px;color:#fff;background:#154b36;font-size:15px;font-weight:700}.motion-preview .progress-motion{min-height:284px}.motion-preview .progress-motion svg{width:100%;max-width:470px;height:282px}'''
frames=[];errors=[];cycles=[]
with sync_playwright() as p:
 browser=p.chromium.launch(channel='msedge',headless=True)
 page=browser.new_page(viewport={'width':580,'height':416},device_scale_factor=1,reduced_motion='no-preference')
 page.on('pageerror',lambda error:errors.append(str(error)));page.route('**/*',lambda route:route.abort())
 page.set_content(markup);page.add_style_tag(content=css);page.add_style_tag(content=style);page.add_script_tag(content=source)
 stages=[('prepare','環境の確認',1.7),('audio','音声の前処理',2.1),('transcribe','文字起こし',2.6),('align','発話時刻の補正',2.6),('speakers','話者の分離',3.0),('edit','文章の仕上げ',2.4),('save','結果の保存',2.4),('complete','完了',1.3)]
 for scene,title,duration in stages:
  page.evaluate('''({scene,title})=>{document.querySelector('#preview-title').textContent=title;updateProgressMotion(document.querySelector('#preview-motion'),{identity:'preview',stage:scene,scene,state:scene==='complete'?'completed':'running'})}''',{'scene':scene,'title':title})
  start=time.perf_counter()
  for frame in range(math.ceil(duration*10)):
   cycle=page.evaluate('''()=>{const state=document.querySelector('#preview-motion').dataset.cycle;document.querySelector('#preview-cycle').textContent={startup:'起動',transition:'切替',loop:'繰り返し',settling:'完了へ',settled:'完了',waiting:'待機'}[state]||state;return state}''')
   cycles.append(cycle)
   shot=page.screenshot();frames.append(Image.open(BytesIO(shot)).convert('RGB'))
   if scene=='transcribe' and frame==15:frames[-1].save(out/'motion-theme-preview.png')
   wait=(frame+1)/10-(time.perf_counter()-start)
   if wait>0:time.sleep(wait)
 assert {'startup','transition','loop','settled'}.issubset(set(cycles)),set(cycles)
 assert not errors,errors
 browser.close()
palette=frames[50].convert('P',palette=Image.Palette.ADAPTIVE,colors=160)
encoded=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
target=out/'gurumoji-common-motion.gif'
encoded[0].save(target,save_all=True,append_images=encoded[1:],duration=100,loop=0,optimize=True,disposal=2)
result={'result':'passed','gif':str(target),'frames':len(frames),'bytes':target.stat().st_size,'cycles':sorted(set(cycles)),'errors':errors}
(out/'preview-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))

"""実データや実サービスを使わず、現行の画面部品をEdgeで操作する。"""
import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
app_dir = args.source_root / "src/gurumoji"
app = __import__("runpy").run_path(str(Path(__file__).resolve().parents[1] / "app_source.py"))["read_app_source"](app_dir / "static")
effort = (app_dir / "static/ai-effort.js").read_text(encoding="utf-8")
template = (app_dir / "templates/views/create.html").read_text(encoding="utf-8")
template = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", "", template, flags=re.S)


def function(name):
    start = app.index(f"function {name}(")
    end = app.find("\nfunction ", start + 1)
    return app[start:end]


bootstrap = """
const tokenConfigSnapshot={lmstudio:true,lmstudio_model:'fixture-local',typesafe:true,typesafe_model:'fixture-jev',huggingface:true,
transcription_readiness:{whisperx:{blockers:[],notes:['話者分離モデルの確認が必要です'],models:{cpu:{base:{status:'cached',message:'base / CPU: キャッシュあり'}}}}}};
const configLoadState='loaded',jobRunning=false;
let apiCalls=0;
function apiFetch(){apiCalls++;return Promise.resolve({ok:true,json:async()=>({model:'fixture-local',reasoning:{}})});}
function hasSelectedSource(){return true;}
function readSeenNotices(){return new Set();}
function selectedConversationMode(){return 'meeting';}
const conversationModePresets={meeting:{label:'会議'}};
function isSpeakerCountFixed(){return false;}
function vocabularyTermsFromInput(){return [];}
function renderMobileWizard(){}
function listen(node,event,callback){node?.addEventListener(event,callback);}
function syncAiFields(){syncAiEffortSettings();}
const fileDropZone=null,pathDetail=null,inputFile=null,sourcePath=null;
const aiProvider=document.querySelector('#ai-provider'),cleanTranscript=document.querySelector('#clean-transcript'),detectNames=document.querySelector('#detect-names'),createOutline=document.querySelector('#create-outline'),jevCompare=document.querySelector('#jev-compare'),finishInObsidian=document.querySelector('#finish-in-obsidian');
const transcriptFinishingModeInputs=[...document.querySelectorAll('[name="transcript_finishing_mode"]')],finishingModeHint=null;
const transcriptionBackend={value:'whisperx'},modelName={value:'base',options:[],selectedIndex:-1},languageSelect=null,audioPreprocess={value:'standard',options:[],selectedIndex:-1};
const triplePass=null,emotionAnalysis=null,emotionModel=null,writeSrt=null,burnSubtitledVideo=null,startButton=null;
const setupReadyState=document.querySelector('#setup-ready-state'),setupSummary=document.querySelector('#setup-summary');
document.querySelector('#ai-provider').value='lmstudio';
document.querySelector('#finish-in-obsidian').checked=false;
"""
functions = "\n".join(function(n) for n in (
    "transcriptFinishingPlan", "enabledTextDestinations", "createReadiness",
    "updateCreateSummary", "selectedOptionText", "setAlert",
))
mode_start = app.index("function selectedTranscriptFinishingMode(")
mode_end = app.index("function selectDefaultAiOptions(", mode_start)
event_start = app.index("transcriptFinishingModeInputs.forEach(input => listen(input, 'change'")
event_end = app.index("[modelName, languageSelect, audioPreprocess, writeSrt", event_start)
script = bootstrap + functions + app[mode_start:mode_end] + effort + app[event_start:event_end] + """
document.addEventListener('change',()=>{syncAiEffortSettings();updateCreateSummary();});
updateCreateSummary();
"""
args.output.mkdir(parents=True, exist_ok=True)
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1360, "height": 1000})
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/*", lambda route: route.abort())
    page.set_content('<meta charset="utf-8">' + template)
    page.add_style_tag(content=(app_dir / "static/ai-effort.css").read_text(encoding="utf-8"))
    page.add_script_tag(content=script)
    page.evaluate("document.querySelector('#panel-finishing').open=true")
    page.wait_for_function("localEffortState==='loaded'")
    page.locator('#detect-names').uncheck()
    text = page.locator('#setup-readiness-details').inner_text()
    assert '文章の仕上げ' in text and '話者名を確認:' not in text and '話者を再確認:' not in text
    assert 'TypeSafe' in page.locator('[data-text-destinations]').first.inner_text()
    page.locator('#effort-select-cleanup').select_option('off', force=True)
    assert '送信なし' in page.locator('[data-text-destinations]').first.inner_text()
    assert '文章の仕上げ:' not in page.locator('#setup-readiness-details').inner_text()
    assert '話者分離モデル' in page.locator('#setup-readiness-details').inner_text()
    page.locator('#detect-names').check()
    assert 'fixture-local' in page.locator('[data-text-destinations]').first.inner_text()
    assert 'TypeSafe' not in page.locator('[data-text-destinations]').first.inner_text()
    assert '話者名を確認／話者を再確認:' in page.locator('#setup-readiness-details').inner_text()
    page.locator('[name="transcript_finishing_mode"][value="off"]').check()
    assert '送信なし' in page.locator('[data-text-destinations]').first.inner_text()
    assert page.locator('#effort-capability-retry').is_hidden()
    assert '話者名を確認:' not in page.locator('#setup-readiness-details').inner_text()
    page.locator('[name="transcript_finishing_mode"][value="recommended"]').check()
    assert page.locator('#detect-names').is_checked()
    page.locator('#detect-names').uncheck()
    page.locator('#effort-select-cleanup').select_option('medium', force=True)
    page.locator('#finish-in-obsidian').check()
    assert '送信なし' in page.locator('[data-text-destinations]').first.inner_text()
    assert '文章の仕上げ:' not in page.locator('#setup-readiness-details').inner_text()
    for stylesheet in ('style.css', 'stitch-theme.css'):
        page.add_style_tag(content=(app_dir / 'static' / stylesheet).read_text(encoding='utf-8'))
    page.evaluate("""() => {
      tokenConfigSnapshot.huggingface=false;
      tokenConfigSnapshot.transcription_readiness.whisperx.notes=['Hugging Faceのモデル利用条件への同意状況と、トークンのアクセス権限は未確認です。話者分離と発話時刻の調整に使うモデルも未確認のため、開始時に接続確認やダウンロードが必要になる場合があります'];
      tokenConfigSnapshot.transcription_readiness.whisperx.models.cpu.base={status:'unknown',message:'large-v3 / CUDA: モデルの準備状況は未確認です。お使いのGPUに応じた形式のモデルを読み込みます'};
      document.querySelector('#detect-names').checked=true;
      document.querySelector('#setup-launch').classList.add('confirm-open');
      syncAiEffortSettings();updateCreateSummary();
    }""")
    warning=page.locator('#setup-readiness-details')
    assert warning.locator('section').count()==2
    assert warning.locator('section').nth(0).locator('li').count()==1
    assert warning.locator('section').nth(1).locator('li').count()==3
    assert '有効OFF' not in warning.inner_text()
    assert 'OFFを選択していても' not in warning.inner_text()
    page.evaluate("setAiEffortChoice('name_extract','off');setAiEffortChoice('name_verify','off');updateCreateSummary()")
    assert warning.locator('section').nth(1).locator('li').count()==3
    assert warning.inner_text().count('OFFを選択していても')==1
    assert warning.evaluate('(el)=>el.scrollWidth<=el.clientWidth')
    warning.screenshot(path=str(args.output / 'readiness-copy-1360.png'))
    page.screenshot(path=str(args.output / 'finishing-readiness-1360.png'), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.evaluate("document.querySelector('#job-form').classList.replace('mobile-step-1','mobile-step-3')")
    assert warning.evaluate('(el)=>el.scrollWidth<=el.clientWidth')
    warning.screenshot(path=str(args.output / 'readiness-copy-390.png'))
    page.screenshot(path=str(args.output / 'finishing-readiness-390.png'), full_page=True)
    assert not errors, errors
    result = {"result": "passed", "scope": "実画面部品の機能切替・注意文・送信先・要約", "page_errors": errors, "model_calls": "mock"}
    (args.output / 'browser-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    browser.close()

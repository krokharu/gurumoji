"""合成データと合成音声だけで開発版の話者タイムラインをEdgeで検証する。"""
import argparse
import io
import json
import subprocess
import sys
import wave
from pathlib import Path
from urllib.parse import unquote, urlparse
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument("--source-root", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = args.source_root.resolve()
args.output.mkdir(parents=True, exist_ok=True)
fixture = Path(__file__).resolve().parents[1] / "dom/render_fixture.py"
html = subprocess.check_output([sys.executable, str(fixture), str(root)], encoding="utf-8")
static = root / "src/gurumoji/static"
wav = io.BytesIO()
with wave.open(wav, "wb") as audio:
    audio.setnchannels(1)
    audio.setsampwidth(2)
    audio.setframerate(8000)
    audio.writeframes(b"\0\0" * 8000 * 120)
synthetic = dict(
    id="timeline-fixture", status="completed", source_name="合成会議.wav",
    revision_count=1, files=[], media_url="/synthetic.wav", media_kind="audio",
    speaker_names={"A": "司会", "B": "参加者", "__proto__": "<img src=x onerror=alert(1)>"},
    speaker_profiles={}, session_profile={},
    segments=[
        dict(id="a1", speaker="A", start=0, end=12, text="導入の発話"),
        dict(id="a2", speaker="A", start=8, end=20, text="同じ話者の重なり"),
        dict(id="b1", speaker="B", start=10, end=35, text="参加者の発話"),
        dict(id="b2", speaker="B", start=50, end=75, text="後半の発話"),
        dict(id="p1", speaker="__proto__", start=80, end=90, text="<script>安全な表示</script>"),
        dict(id="missing", speaker="B", start=0, end=0, time_unknown=True, text="時刻不明"),
        dict(id="invalid", speaker="B", start=-3, end=5, text="不正時刻"),
        dict(id="string", speaker="B", start="6", end="9", text="数値文字列"),
    ],
    outline=dict(sections=[
        dict(start=0, end=40, title="導入と背景", summary="合成の要約"),
        dict(start=40, end=90, title="意見とまとめ", summary="合成の要約"),
    ]),
)
errors, external, writes = [], [], []
checks = []
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport=dict(width=1440, height=1050), reduced_motion="reduce")
    page.add_init_script("sessionStorage.setItem('gurumoji.bootSplashSeen','1');")
    page.on("pageerror", lambda error: errors.append(str(error)))

    def route(req):
        parsed = urlparse(req.request.url)
        path = unquote(parsed.path)
        if parsed.hostname != "gurumoji.invalid":
            external.append(req.request.url)
            req.abort()
            return
        if req.request.method not in ("GET", "HEAD"):
            writes.append(path)
        if path == "/":
            req.fulfill(body=html, content_type="text/html")
        elif path == "/synthetic.wav":
            req.fulfill(body=wav.getvalue(), content_type="audio/wav", headers={"Accept-Ranges": "bytes"})
        elif path.startswith("/static/"):
            file = (static / path.removeprefix("/static/")).resolve()
            if static in file.parents and file.is_file():
                req.fulfill(path=str(file))
            else:
                req.fulfill(status=404, body="")
        elif path.startswith("/api/"):
            data = {}
            if path == "/api/config":
                data = dict(ok=True, runtime=dict(browser_upload=True))
            elif path == "/api/jobs/active":
                data = {"job": None}
            elif path == "/api/library":
                data = dict(items=[], pagination=dict(offset=0, limit=50, total=0, has_more=False))
            elif path == "/api/library/timeline-fixture":
                data = synthetic
            elif path == "/api/speakers":
                data = dict(speakers=[], registry_revision=0)
            elif path == "/api/custom-vocabulary":
                data = {"terms": []}
            elif path == "/api/training":
                data = dict(event_count=0, ready_count=0)
            elif path == "/api/obsidian/obussql":
                data = dict(available=False, status="disabled")
            req.fulfill(json=data)
        else:
            req.abort()

    page.route("**/*", route)
    page.goto("https://gurumoji.invalid/#/new")
    page.wait_for_function("configLoadState === 'loaded'")
    page.evaluate("(job) => renderResult(job)", synthetic)
    panel = page.locator("#speaker-timeline")
    expect(panel).to_be_visible()
    page.wait_for_function("mediaPlayer.duration === 120")
    expect(page.locator(".timeline-row-segment")).to_have_count(3)
    expect(page.locator(".timeline-row-outline")).to_have_count(1)
    expect(page.locator(".timeline-row-outline .timeline-block")).to_have_count(2)
    expect(page.locator(".timeline-row-segment .timeline-block")).to_have_count(5)
    expect(page.locator("#timeline-notice")).to_contain_text("3件")
    assert page.locator(".timeline-row-segment").first.locator(".timeline-lane").evaluate("(el)=>el.clientHeight") >= 80
    assert page.locator("#timeline-canvas img, #timeline-canvas script").count() == 0
    assert page.locator("#timeline-canvas").evaluate("(el)=>el.innerHTML.includes('NaN')") is False
    original = page.evaluate("JSON.stringify(currentJob.segments)")
    page.evaluate("renderSpeakerTimeline()")
    assert page.evaluate("JSON.stringify(currentJob.segments)") == original
    checks.append("話者別の行、重複区間、欠測除外、安全な表示、元データ非変更")

    # 発話選択は絞り込みを解除し、指定した発話の開始位置から再生する。
    page.locator("#segment-keyword").fill("一致なし")
    page.locator(".timeline-block[data-segment-id='b2']").click()
    page.wait_for_function("selectedSegmentId === 'b2' && mediaPlayer.currentTime >= 50 && mediaPlayer.currentTime < 53")
    expect(page.locator(".segment.selected")).to_have_attribute("data-segment-id", "b2")
    expect(page.locator("#segment-keyword")).to_have_value("")
    page.evaluate("mediaPlayer.pause()")
    assert page.evaluate("playbackStopAt") is None
    page.locator(".timeline-row-outline .timeline-block").last.click()
    page.wait_for_function("mediaPlayer.currentTime >= 40 && mediaPlayer.currentTime < 43")
    page.evaluate("mediaPlayer.pause()")
    page.locator("#timeline-seek").focus()
    page.locator("#timeline-seek").press("ArrowRight")
    assert page.evaluate("mediaPlayer.currentTime") >= 40.1
    checks.append("発話・アウトラインからの再生、絞り込み解除、キーボードでの移動")

    page.evaluate("mediaPlayer.currentTime=55; syncMediaPlayback(55)")
    expect(page.locator(".timeline-block[data-segment-id='b2']")).to_have_class("timeline-block is-selected is-playing")
    page.locator("#timeline-zoom").select_option("8")
    assert page.locator("#timeline-viewport").evaluate("(el)=>el.scrollWidth > el.clientWidth * 5")
    assert page.locator("#timeline-viewport").evaluate("(el)=>el.scrollLeft > 0")
    page.locator("#timeline-current").click()
    checks.append("再生中の強調、再生ヘッド、拡大と横スクロール")

    # タイムライン操作中は本文へ飛ばさず、本文からの再生では従来の追従を維持する。
    page.evaluate("window.scrollTo(0,0); window.scrollCalls=[]; window.oldScroll=Element.prototype.scrollIntoView; Element.prototype.scrollIntoView=function(){window.scrollCalls.push(String(this.className || ''))}")
    page.locator("#timeline-zoom").select_option("1")
    page.locator("[data-segment-id='b2'].timeline-block").click()
    page.evaluate("mediaPlayer.pause()")
    assert page.evaluate("window.scrollCalls.filter(name=>name.includes('segment')).length") == 0
    page.evaluate("playSegment('b2'); syncMediaPlayback(45); syncMediaPlayback(55); mediaPlayer.pause()")
    assert page.evaluate("window.scrollCalls.some(name=>name.includes('segment'))")
    page.evaluate("() => {Element.prototype.scrollIntoView=window.oldScroll;}")
    checks.append("タイムライン再生時は本文への自動スクロールを抑制、本文再生時は既存の追従を維持")

    # 既存の編集UIから時刻・本文・話者・話者名・色を変更する。
    page.locator(".segment.selected input[data-segment-field='start']").fill("48")
    page.locator(".segment.selected input[data-segment-field='start']").dispatch_event("change")
    page.locator(".segment.selected textarea[data-segment-field='text']").fill("編集済みの発話")
    expect(page.locator(".timeline-block[data-segment-id='b2']")).to_have_text("編集済みの発話")
    page.locator(".segment.selected select[data-segment-field='speaker']").select_option("A")
    expect(page.locator(".timeline-row-segment").first.locator("[data-segment-id='b2']")).to_have_count(1)
    page.locator("#item-tab-conversation").click()
    name = page.locator("[data-speaker-label='A'][data-speaker-field='display_name']")
    name.fill("進行役")
    theme = page.locator("[data-speaker-label='A'][data-speaker-field='theme_color']")
    theme.fill("#654321")
    theme.dispatch_event("input")
    page.locator("#item-tab-transcript").click()
    expect(page.locator(".timeline-row-segment").first.locator(".timeline-label")).to_have_text("進行役")
    assert page.locator(".timeline-row-segment").first.evaluate("(el)=>el.style.getPropertyValue('--timeline-accent')").lower() == "#654321"
    checks.append("既存UIの本文・時刻・話者・話者名・色の編集に追従")

    page.locator("#add-segment-button").click()
    added_id = page.evaluate("selectedSegmentId")
    expect(page.locator(".timeline-row-segment .timeline-block")).to_have_count(6)
    page.locator(".segment.selected .segment-delete").click()
    expect(page.locator(".timeline-row-segment .timeline-block")).to_have_count(5)
    page.locator("#undo-segment-delete").click()
    expect(page.locator(".timeline-row-segment .timeline-block")).to_have_count(6)
    assert page.evaluate("selectedSegmentId") == added_id
    checks.append("発話の追加・削除・元に戻すに追従")

    page.locator("#timeline-zoom").select_option("1")
    panel.screenshot(path=str(args.output / "timeline-desktop.png"))
    page.set_viewport_size(dict(width=390, height=844))
    page.wait_for_timeout(150)
    assert panel.bounding_box()["width"] <= 390
    assert page.locator("#timeline-viewport").evaluate("(el)=>el.scrollWidth <= el.clientWidth + 1")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    panel.screenshot(path=str(args.output / "timeline-mobile.png"))
    checks.append("1440px・390pxの表示と画面の横はみ出し防止")

    # 統合アウトラインを優先し、データ切り替えで再生位置・拡大率を初期化する。
    joined = dict(synthetic, id="timeline-other", media_url=None, session_outline=dict(result=dict(
        rows=[dict(start=0, end=90, title="統合した議題")], transformer_stale=True)))
    page.evaluate("(job)=>renderResult(job)", joined)
    expect(page.locator(".timeline-row-outline .timeline-block")).to_have_count(1)
    expect(page.locator(".timeline-row-outline .timeline-block")).to_be_disabled()
    expect(page.locator("#timeline-notice")).to_contain_text("編集前")
    expect(page.locator("#timeline-seek")).to_be_disabled()
    expect(page.locator("#timeline-zoom")).to_have_value("1")
    page.locator("[data-segment-id='a1'].timeline-block").click()
    assert page.evaluate("selectedSegmentId") == "a1"
    page.evaluate("(job)=>renderResult(job)", dict(synthetic, id="timeline-empty", media_url=None, segments=[], outline=None))
    expect(page.locator("#timeline-seek")).to_be_disabled()
    expect(page.locator("#timeline-notice")).to_contain_text("発話はまだありません")
    # 0秒だけの発話と不正アウトラインでもNaN座標を生成しない。
    page.evaluate("(job)=>renderResult(job)", dict(synthetic, id="timeline-zero", media_url=None,
        segments=[dict(id="zero", speaker="A", start=0, end=0, text="ゼロ秒")],
        outline=dict(sections=[dict(start=0, end=0, title="ゼロ秒議題")])))
    assert not page.locator("#timeline-canvas").evaluate("(el)=>/NaN|Infinity/.test(el.innerHTML)")
    checks.append("統合アウトライン優先、古い分析の明示、メディアなし、空状態、0秒、データ切り替え")

    # 長時間の会話でも最大拡大率の幅を制限し、再生位置へ移動できる。
    long_job = dict(synthetic, id="timeline-long", media_url=None,
        segments=[dict(id="long", speaker="A", start=7190, end=7200, text="2時間後の発話")],
        outline=dict(sections=[dict(start=0, end=7200, title="長時間の議題")]))
    page.evaluate("(job)=>renderResult(job)", long_job)
    page.locator("#timeline-zoom").select_option("32")
    assert page.locator("#timeline-canvas").evaluate("(el)=>el.scrollWidth") <= 200152
    expect(page.locator("#timeline-position")).to_contain_text("02:00:00")
    page.evaluate("(job)=>renderResult(job)", dict(synthetic, id="timeline-video", media_kind="video"))
    expect(page.locator("#media-player-host video")).to_have_count(1)
    page.wait_for_function("mediaPlayer.duration === 120")
    page.locator(".timeline-block[data-segment-id='b2']").click()
    page.wait_for_function("mediaPlayer.currentTime >= 50 && mediaPlayer.currentTime < 53")
    page.evaluate("mediaPlayer.pause()")
    checks.append("2時間の会話、最大拡大率の幅制限、動画プレイヤーとの連動")

    assert errors == [], errors
    assert external == [], external
    assert writes == [], writes
    browser.close()
report = dict(checks=checks, errors=errors, external_requests=external, writes=writes)
(args.output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))

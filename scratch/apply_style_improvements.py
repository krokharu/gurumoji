path = "src/gurumoji/static/style.css"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. --text-min: .7rem; -> --text-min: .82rem;
if "--text-min: .7rem;" in content:
    content = content.replace("--text-min: .7rem;", "--text-min: .82rem;", 1)
    print("Updated --text-min")

# 2. .transcript-layout
old_layout = "minmax(300px, 380px) minmax(0, 1fr)"
new_layout = "minmax(380px, 480px) minmax(0, 1fr)"
if old_layout in content:
    content = content.replace(old_layout, new_layout, 1)
    print("Updated .transcript-layout columns")

# 3. .media-review とコントロール
old_media_review = """.media-review { margin-bottom: 28px; padding: 20px; border-radius: 18px; background: #17201c; color: white; }
.media-review-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.media-review-head .eyebrow { margin-bottom: 5px; color: var(--lime); }
.context-field { width: 100px; }
.context-field > span { color: #bfc9c3; }
.context-field select { min-height: 38px; }
.media-player-host audio, .media-player-host video { display: block; width: 100%; max-height: 430px; border-radius: 11px; background: #090d0b; }
.media-controls { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 13px; }
.media-controls .secondary-button { min-height: 40px; padding: 0 14px; border-color: #56615c; background: #28322d; color: white; }"""

new_media_review = """.media-review { margin-bottom: 24px; padding: 18px 20px; border: 1px solid var(--line); border-radius: 18px; background: var(--card); box-shadow: var(--shadow-soft); color: var(--ink); }
.media-review-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.media-review-head .eyebrow { margin-bottom: 5px; color: var(--green); }
.media-review-head .media-review-kicker { color: var(--green); }
.context-field { width: 100px; }
.context-field > span { color: var(--muted); }
.context-field select { min-height: 38px; border-color: var(--line); background: white; color: var(--ink); }
.media-player-host audio, .media-player-host video { display: block; width: 100%; max-height: 460px; border-radius: 11px; background: #0e1411; border: 1px solid #1f2a24; }
.media-controls { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; margin-top: 13px; }
.media-controls .secondary-button { min-height: 38px; padding: 0 12px; border-color: var(--line); background: white; color: var(--ink); font-size: .8rem; }
.media-controls .secondary-button:hover { border-color: var(--green); color: var(--green); }
.media-autoscroll-label { display: inline-flex; align-items: center; gap: 6px; font-size: .8rem; font-weight: 700; color: var(--muted); cursor: pointer; user-select: none; margin-left: auto; }
.media-autoscroll-label input { cursor: pointer; }"""

if old_media_review in content:
    content = content.replace(old_media_review, new_media_review, 1)
    print("Updated .media-review styles")
else:
    print("Warning: old_media_review not found exactly")

# 4. .segment の通常時・展開時・アクティブ時のスタイル
old_segment_block = """.segment { display: grid; grid-template-columns: 170px minmax(0, 1fr); gap: 18px; padding: 18px; border: 1px solid var(--line); border-radius: 14px; background: white; }
.segment.selected { border-color: var(--green); box-shadow: 0 0 0 3px rgba(28,107,80,.1); }
.segment-meta { display: flex; align-items: flex-start; flex-direction: column; gap: 8px; }
.segment-time { color: var(--muted); font: .72rem/1 Consolas, monospace; }
.segment-speaker { padding: 6px 8px; border: 2px solid transparent; border-radius: 7px; background: #e5eee5; color: var(--green); font-size: .72rem; font-weight: 800; }
.segment-emotion { padding: 6px 8px; border-radius: 7px; background: #f3eadb; color: #7c4d22; font-size: .72rem; font-weight: 800; }
.segment-jev-badge { padding: 6px 8px; border-radius: 7px; background: #e9f2e5; color: #315f40; font-size: var(--text-min); font-weight: 900; }
.segment-jev-badge.current_only, .segment-jev-badge.jev_only { background: #fff0de; color: #8a4e22; }
.segment-jev-badge.both_flagged { background: #f5dfdc; color: #913733; }
.segment-play, .segment-delete { min-height: 34px; padding: 0 10px; border: 1px solid #cbd2cb; border-radius: 8px; background: white; color: var(--green); font-size: .72rem; font-weight: 800; }
.segment-delete { color: var(--red); }
.segment-body { display: grid; gap: 10px; }
.segment-ai-review { padding: 10px; border-radius: 7px; background: #f3eadb; color: #644522; font-size: .85rem; }
.segment-ai-review summary { cursor: pointer; font-weight: 700; }
.segment-ai-review p { white-space: pre-wrap; overflow-wrap: anywhere; }
.segment-jev-review { padding: 10px; border-radius: 7px; background: #edf4e9; color: #31533b; font-size: .82rem; }
.segment-jev-review summary { cursor: pointer; font-weight: 800; }
.segment-jev-review p { margin: 8px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.segment-fields { display: grid; grid-template-columns: 110px 110px minmax(130px, .8fr) minmax(130px, .8fr); gap: 9px; }
.segment-fields .field input, .segment-fields .field select { min-height: 39px; }
.segment textarea { width: 100%; min-height: 84px; padding: 12px 14px; resize: vertical; border: 1px solid #d0d5cf; border-radius: 10px; outline: none; line-height: 1.7; }"""

new_segment_block = """/* --- セグメント（通常時：コンパクトなタイムライン／チャット風） --- */
.segment {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 8px 14px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: white;
  cursor: pointer;
  transition: border-color .15s, box-shadow .15s, background-color .15s;
}
.segment:hover {
  border-color: #b5c4b8;
  background: #fbfdf9;
}
.segment-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.segment-time { color: var(--muted); font: .78rem/1 Consolas, monospace; }
.segment-speaker { padding: 4px 7px; border: 2px solid transparent; border-radius: 6px; background: #e5eee5; color: var(--green); font-size: .76rem; font-weight: 800; white-space: nowrap; }
.segment-emotion { padding: 4px 6px; border-radius: 6px; background: #f3eadb; color: #7c4d22; font-size: .72rem; font-weight: 800; }
.segment-jev-badge { padding: 4px 6px; border-radius: 6px; background: #e9f2e5; color: #315f40; font-size: var(--text-min); font-weight: 900; }
.segment-jev-badge.current_only, .segment-jev-badge.jev_only { background: #fff0de; color: #8a4e22; }
.segment-jev-badge.both_flagged { background: #f5dfdc; color: #913733; }
.segment-play, .segment-delete { min-height: 32px; padding: 0 9px; border: 1px solid #cbd2cb; border-radius: 7px; background: white; color: var(--green); font-size: .74rem; font-weight: 800; white-space: nowrap; }
.segment-delete { color: var(--red); }
.segment-body { display: grid; gap: 8px; min-width: 0; }

/* 通常時（折りたたみ）はフィールドとAIレビュー詳細を隠し、テキストを1行プレビュー表示 */
.segment:not(.selected) .segment-fields,
.segment:not(.selected) .segment-ai-review,
.segment:not(.selected) .segment-jev-review,
.segment:not(.selected) .segment-delete {
  display: none !important;
}
.segment:not(.selected) textarea {
  width: 100%;
  min-height: 36px;
  height: 36px;
  padding: 6px 8px;
  resize: none;
  font-size: .88rem;
  line-height: 1.45;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}
.segment:not(.selected):hover textarea {
  background: #f3f7f1;
}

/* --- セグメント（選択・編集時：フル展開） --- */
.segment.selected {
  display: grid;
  grid-template-columns: 170px minmax(0, 1fr);
  align-items: start;
  gap: 16px;
  padding: 16px;
  border-color: var(--green);
  box-shadow: 0 0 0 3px rgba(28,107,80,.12), var(--shadow-soft);
  background: white;
  cursor: default;
}
.segment.selected .segment-meta {
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
.segment.selected .segment-delete {
  display: inline-flex !important;
}
.segment.selected .segment-fields {
  display: grid !important;
}
.segment.selected textarea {
  min-height: 84px;
  height: auto;
  padding: 12px 14px;
  resize: vertical;
  border: 1px solid #d0d5cf;
  border-radius: 10px;
  outline: none;
  line-height: 1.7;
  font-size: .92rem;
  background: white;
  white-space: normal;
  cursor: text;
}
.segment.selected textarea:focus {
  border-color: var(--green);
}

/* 再生中ハイライト */
.segment.is-active-playback {
  border-color: var(--orange) !important;
  background: #fffdf7 !important;
  box-shadow: 0 0 0 2px rgba(232, 121, 65, 0.35) !important;
}

.segment-ai-review { padding: 10px; border-radius: 7px; background: #f3eadb; color: #644522; font-size: .85rem; }
.segment-ai-review summary { cursor: pointer; font-weight: 700; }
.segment-ai-review p { white-space: pre-wrap; overflow-wrap: anywhere; }
.segment-jev-review { padding: 10px; border-radius: 7px; background: #edf4e9; color: #31533b; font-size: .82rem; }
.segment-jev-review summary { cursor: pointer; font-weight: 800; }
.segment-jev-review p { margin: 8px 0 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.segment-fields { display: grid; grid-template-columns: 110px 110px minmax(130px, .8fr) minmax(130px, .8fr); gap: 9px; }
.segment-fields .field input, .segment-fields .field select { min-height: 39px; }"""

if old_segment_block in content:
    content = content.replace(old_segment_block, new_segment_block, 1)
    print("Updated .segment styles")
else:
    print("Warning: old_segment_block not found exactly")

# 5. プログレスカードのアコーディオンと波形アニメーション調整
accordion_css = """
/* ---------- Progress details accordion ---------- */
.progress-details-accordion {
  margin-top: 20px;
  border: 1px solid #dce4da;
  border-radius: 14px;
  background: #fbfdf9;
  overflow: hidden;
}
.progress-details-accordion summary {
  padding: 12px 16px;
  font-size: .84rem;
  font-weight: 700;
  color: var(--green-dark);
  cursor: pointer;
  background: #f4f8f2;
  user-select: none;
  outline: none;
  transition: background-color .15s;
}
.progress-details-accordion summary:hover {
  background: #ebf3e8;
}
.progress-details-accordion[open] summary {
  border-bottom: 1px solid #dce4da;
}
.progress-details-body {
  padding: 14px 16px;
}
.progress-details-body .ai-token-usage {
  margin-top: 0;
}
.progress-details-body .resource-monitor {
  margin-top: 14px;
}
.progress-details-body .log-details {
  margin-top: 14px;
}
"""

# 波形アニメーション調整
content = content.replace(
    "to { height: 38px; opacity: 1; }",
    "to { height: 26px; opacity: .88; }",
    1
)
content = content.replace(
    "animation: process-wave .72s ease-in-out infinite alternate;",
    "animation: process-wave 1.1s ease-in-out infinite alternate;",
    1
)

# 末尾に accordion_css を追加
content += accordion_css
print("Added progress details accordion css")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Finished updating style.css")

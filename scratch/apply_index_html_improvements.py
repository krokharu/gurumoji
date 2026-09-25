import re

path = "src/gurumoji/templates/index.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. session-outline の open 属性を削除
# <details id="session-outline" class="session-outline" open> -> <details id="session-outline" class="session-outline">
old_outline = '<details id="session-outline" class="session-outline" open>'
new_outline = '<details id="session-outline" class="session-outline">'
if old_outline in content:
    content = content.replace(old_outline, new_outline, 1)
    print("Updated session-outline open state")
else:
    print("Warning: old_outline not found")

# 2. media-controls に 自動追従 チェックボックスを追加
old_media_controls = '''              <div class="media-controls">
                <button id="previous-segment-button" class="secondary-button" type="button">← 前の発話</button>
                <button id="replay-segment-button" class="secondary-button" type="button">選択箇所を再生</button>
                <button id="next-segment-button" class="secondary-button" type="button">次の発話 →</button>
              </div>'''

new_media_controls = '''              <div class="media-controls">
                <button id="previous-segment-button" class="secondary-button" type="button">← 前の発話</button>
                <button id="replay-segment-button" class="secondary-button" type="button">選択箇所を再生</button>
                <button id="next-segment-button" class="secondary-button" type="button">次の発話 →</button>
                <label class="mini-check media-autoscroll-label"><input id="media-autoscroll" type="checkbox" checked><span>自動追従</span></label>
              </div>'''

if old_media_controls in content:
    content = content.replace(old_media_controls, new_media_controls, 1)
    print("Updated media-controls with autoscroll")
else:
    print("Warning: old_media_controls not found")

# 3. progress-card のシステム計器・AIトークン・ログをアコーディオンに格納
# 対象範囲: <section id="progress-ai-usage" ... から <details class="log-details">...</details> まで
target_pattern = r'(<section id="progress-ai-usage".*?</details>)'
match = re.search(target_pattern, content, re.DOTALL)
if match:
    original_block = match.group(1)
    # これを details でラップする
    wrapped_block = f'''<details id="progress-system-details" class="progress-details-accordion">
          <summary>詳細システム情報とログ（AIトークン使用量 / システム負荷 / 処理ログ）</summary>
          <div class="progress-details-body">
{original_block}
          </div>
        </details>'''
    content = content.replace(original_block, wrapped_block, 1)
    print("Wrapped progress-card details in accordion")
else:
    print("Warning: progress-card details block not matched")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Finished updating index.html")

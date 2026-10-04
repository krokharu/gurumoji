# Browser test workflow

`browser_support.py` は既存browser試験の起動境界。アプリ、fixtureのAI stub、
合成DB、marker/assertionの意味は変えない。

## 通常の回帰実行

`GURUMOJI_RUN_UI_BROWSER` 未設定時はbrowser class/methodだけをfixture開始前に
`not-run` としてskipする。API試験は実行する。直接launcherを呼んでもopt-inが必要。

```bash
env -u GURUMOJI_RUN_UI_BROWSER PYTHONPATH=src:tests python -m unittest \
  test_browser_support test_browser_e2e test_analysis_method_view \
  test_content_browser test_qualitative_visualization test_transcript_preparation \
  test_transformer_content_browser test_ui_safety_browser -v
```

`test_browser_support` はprocess/Playwrightをmockした純粋unit試験で、実browserは
起動しない。指定7moduleの危険flag再混入とopt-in適用箇所も静的検査する。

## pytestと開発用scriptの範囲

repo rootの`pytest`（または`python -m pytest`）は`pytest.ini`で`tests/`だけを
既定収集する。`pytest tests/`も同じ正式suite。browserのopt-in/skip条件は同じ。
先に`pytest --collect-only -q`で対象を確認できる。`test_browser_entrypoints`は
rootと明示`tests/`のcollect-only結果を比較し、API試験が残ること、browser/process
を起動しないことを確認する。明示的な別path指定は既定収集設定の対象外。

- `scratch/test_browser_e2e_recovered.py`は退役した履歴stub。収集・実行する試験を
  持たず、直接実行も終了コード2（not-run）。旧実装はGit履歴に保持し、正式coverageは
  `tests/test_browser_e2e.py`だけで管理する
- `scripts/browser_video_input_settings_qa.py`と`scratch/analysis_visual_qa.py before|after`
  は開発用QA。importでは動作しない。起動前に同じ明示opt-inを要求し、共通sandbox付き
  Playwright launcherを使う。未実行/環境blockは終了コード2、検証不一致は1または例外。
  viewport・合成fixture・screenshot出力を維持するが、pytest受入試験とは別に記録する

2026-10-03の旧root実行はscratch重複試験を誤収集し、6 failed / 967 passed /
32 skippedとなった。browser起動はsocket制限等で失敗し、受入成功ではない。
元の`../artifacts/eight-hour-20261003/effort-compatibility-fix/full-tests.txt`と
`result.md`を失敗記録として保持し、この安全化の合格結果に置き換えない。

## Browser実行の前提

明示的な実行許可があり、sandbox付きbrowserが使える環境だけで
`GURUMOJI_RUN_UI_BROWSER=1` を設定する。既に導入済みのChrome/Edge/Chromium、
Playwright試験には既に導入済みのPlaywrightとそのbrowser（または検出済みbrowser）が必要。
helperはbrowser、driver、modelを取得・installしない。

- CLIは固定引数。viewport、仮想時間budget、timeout、媒体fixture用autoplay、
  scale=1だけを名前付きで指定し、任意の追加flagは受け取らない
- CLI profileは必ず呼出元の一時fixture配下に指定し、そのfixtureがcleanupを所有する。
  既存の同一profileでの再読込試験は維持。通常timeoutでは`subprocess.run`が起動processを
  kill/waitし、timeout自体は失敗として扱う
- Playwrightは`chromium_sandbox=True`固定。browser close、driver stopを登録し、
  launch途中やassertion失敗でもcleanupする。contextは各試験がcleanupする
- sandbox/HTTPS/ネットワーク保護の無効化、tunnel、proxy、file URLへの迂回はしない。
  transformerの既存合成file fixtureはcomponent描画契約で、疎通の代替ではない

## 結果の読み方

- `not-run` / skipped: opt-inなし。browser起動なし。UIの成功ではない
- `blocked` / skipped: 任意依存・実行file不足、または明示的なsandbox/namespace/socketの
  起動診断。制約を緩めて再試行しない。理由・環境・未実行caseを残す
- failed/error: marker欠落、JS error、assertion不一致、一般timeout、未知の起動エラー。
  全例外をskipへ変換しない。DOM出力後の不一致も失敗のまま残す
- passed: 実際に実行し期待値を満たした範囲だけ。DOM driver/内部関数による契約試験、
  autoplay媒体state試験を通常操作・ユーザーgesture・支援技術の受入成功とは数えない

browser必須のCIではskip/blocked件数も確認し、未実施をrelease gate成功としない。
この安全化変更のcloud検証はmock、静的検査、API回帰のみ。実browser受入は未実行。

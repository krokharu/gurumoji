"""測定結果を既存Software VaultへUTF-8で記録する。既存本文のbytesを保つ。"""
import ast
import json
from pathlib import Path

root = Path(__file__).resolve().parents[4]
out = root / 'output/validation/obussql-alternatives-20261110'
note = root / 'output/validation/development-assets-20261016/docs/program-vault/60-Operations/20-Development/gurumoji-improvement-session/02-topics/16-section.md'
data = note.read_bytes()
marker = b'\n\n## 2026-11-10: '
position = data.rfind(marker)
title = '公開代替案の実測比較'
# PowerShell既定のASCIIパイプで壊れた今回の追記だけを修復する。
assert position >= 0 and b'??' in data[position:].splitlines()[2]
prefix = data[:position]
record = '''

## 2026-11-10: 公開代替案の実測比較

- 利用者の「それぞれテストして比較した結果を」に基づく実試験。対象は `krokharu/transcription-finish-20261102`、HEAD `d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486` と既存未コミット実装。生成API56応答、投機的デコードの拒否1回、日本語検索25問を検査した。アプリコード、実利用者DB/Vault、認証、共有モデルのロード設定は今回変更していない。モデル一覧とロード設定は取得前後一致。再起動・commit/pushなし。
- 全入力は合成資料。80件の反復表と60件の異種表、ID・数値・否定・例外を変えたholdoutを合わせ4課題。各課題で指定ID2件の条件・例外・整数を完全一致で検査。意味解釈や一般的な研究品質は保証しない。Gemma4 12B QAT、context16384、temperature0、最大出力2048。モデル生成・CPU検索・圧縮の測定は逐次実行し、初期の生成測定中だけ公開重みを取得した。
- 推論6条件はoriginal2課題ずつ。原形式はON32.327秒/推論543.5tokens、短い推論指示32.339秒/557tokens、OFF8.848秒/0tokens。現行混合はON35.697秒/691.5tokens、短い推論29.795秒/575.5tokens、OFF6.325秒/0tokens。すべて2/2一致。native APIでON/OFFを明示し実推論tokensを照合。「短く考える」はOFFの代わりにならない。現行アプリには既にOFF指定の経路があり、以前の既定ONの速度をアプリ通常速度とは扱わない。
- OpenAI互換APIでJSONスキーマを強制した再試験は、原形式が平均入力5942.75tokens/9.488秒/4/4一致、現行混合3454.25/7.173秒/4/4、TOON4746.75/8.409秒/4/4、Python側でIDを照合して資料を絞る方式751.25/6.728秒/4/4。native APIのJSON指示だけの別試験でも4形式とも4/4。2経路は別集計で保持する。現行混合は原形式比で入力41.88%減、スキーマ測定の時間24.40%減。TOONの往復復元も一致したが、現行混合を上回らなかった。
- SQL/Python移管は、モデルにIDだけを返させ、条件・例外・整数は一時SQLiteから原文を復元する方式が712tokens/2.547秒、4/4一致。明示IDだけの定型取得ならAIを呼ばないSQLite照合も4/4で、各課題100回の中央値を平均して0.005825ms。DB作成時間は除く。意味解釈や自由な分析の代替とは扱わない。host.jsonとgeneration.jsonに生結果を保持。
- 検索は合成132文書、文字一致寄り12問・言い換え12問・ID1問の25問で、正解が上位3件に入るかを評価。現行ObusSQL13/25（中央値11.379ms）、文字2gram BM2516/25（0.229ms）、multilingual-e5-small25/25（8.998ms）、BM25+denseのRRF22/25（9.365ms）、RRF+日本語xsmall reranker23/25（32.859ms）、同方式にID優先を足すと24/25（32.862ms）。意味検索+ID優先は25/25、top1は24/25、9.002ms。現行は最後に時系列へ戻すのでtop1を比較せずtop3集合で評価した。複雑な混合・再順位付けが常に良いとは判断しない。
- 検索はCPU4threads。denseロード1.723秒・文書索引0.442秒、rerankerロード0.434秒を検索時間とは別掲。初回6方式の結果はretrieval-initial.jsonへ残し、ID優先のdense候補を追加して7方式を再測定した。小規模の合成コーパスであり、実運用規模・隣接会話・否定の意味解釈・更新時の索引失効は未検証。
- prefix再利用は固定資料を先頭、可変質問を末尾に置いた4組。入力は各6130tokensのまま、TTFT中央値3.836秒から0.423秒、総時間中央値4.037秒から0.489秒。8応答すべてOK。APIにcache命中件数がなく完全coldも保証できないので、応答開始時間の観測結果とする。コンテキスト枠や推論量の削減ではない。
- LLMLingua-2は公開XLM-RoBERTa-large重みをCPUで使用し、rate0.5、数字・否定等のforce保持も指定。平均入力3641tokens、圧縮9.944秒を含め17.753秒（ロード1.017秒は別）。完全一致0/4、対象原文の完全保持0/4。例外が「再検査が陰性ない。」へ欠け、ev-0019のvalue133を19として返した。原文・条件・数値を扱う配送には採用不可。初回accelerate不足は検証用depsへ1.12.0を追加して解消し、4応答を再測定した。初回suite.jsonの失敗を残したままverification.jsonへ復旧を記録。
- 投機的デコードはSDKの予測時draft指定を現行engine protocolが「must be configured at load time, not prediction time」と拒否。共有モデルは再ロードしていない。対応する小型draftも未導入だが、今回の直接原因はロード時設定の要求。速度・品質は未測定で、拒否までの0.312秒を生成性能へ数えない。
- 依存は検証用output配下のdepsだけに固定版を追加し、アプリvenvの依存を更新していない。TOON1.2.0、LLMLingua0.2.2、rank-bm250.2.2、accelerate1.12.0。取得hashはpip-report.json/accelerate-report.json、公開重みのrepo/revisionはmodels.jsonへ保持。rerankerは8547ac84ae5aee35387aad7000b379bd1b968dc6、compressorはebaba9b0e874dadd3003ffcff828e4397e568089。各公開モデルはMIT。e5は既存重みキャッシュを利用し、研究者の本文は使っていない。
- 判断は現行可逆混合と推論OFFを維持し、定型原文・数値取得をSQL/Pythonへ移す案を優先する。検索の次候補はID優先+意味検索。prefix配置も有望だがアプリ全体の実行経路は未実装・未測定。TOONへの置換、LLMLingua-2による原文圧縮、未測定の投機的デコードは採用しない。今回、新案をアプリへ反映していない。
- 各形式・課題は1回ずつで、順序・内部キャッシュの影響が残る。統計的有意差や研究解釈品質は主張しない。証跡は利用者checkoutの `output/validation/obussql-alternatives-20261110/summary.json` とverification.json。生応答はgeneration/structured/host/cache/compression/speculative.json、検索順位はretrieval.json、実装hash・環境版はsummary.json、設定前後はmodels-before/models-after.json。新規評価・記録スクリプト6本のASTと空白を確認した。今回アプリコードを変更していないので、既に完了した170件の回帰試験は再実行していない。
'''
assert '\ufffd' not in record and '??' not in record
note.write_bytes(prefix + record.encode('utf-8'))
assert note.read_bytes()[:len(prefix)] == prefix
assert title in note.read_text(encoding='utf-8')
verification = json.loads((out / 'verification.json').read_text(encoding='utf-8'))
verification['compression_setup_recovery'] = '初回accelerate不足を検証用depsへの1.12.0追加で解消。再測定4応答は完了、完全一致0/4。初回suite.jsonは保持。'
verification['note_utf8_and_prior_bytes_preserved'] = True
verification['scripts_ast_and_whitespace'] = '6 passed'
verification['diff_check'] = '既存の追記部分にCRLF由来の6警告あり。今回追記の末尾空白はなし。既存本文を改変しない。'
for name in ['compare_obussql_external_plans.py', 'test_obussql_retrieval_compression.py', 'prepare_obussql_alternative_models.py',
             'run_obussql_alternatives_suite.py', 'summarize_obussql_alternatives.py', 'record_obussql_alternatives.py']:
    text = Path(__file__).with_name(name).read_text(encoding='utf-8')
    ast.parse(text)
    assert not any(line.rstrip() != line for line in text.splitlines())
assert not any(line.rstrip() != line for line in record.splitlines())
(out / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding='utf-8')
print('Recorded UTF-8 results; earlier bytes preserved; 6 scripts checked.')

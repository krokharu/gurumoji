"""LM Studio実測を生応答と一時SQLで再採点し、既存運用ノートへ残す。"""
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import sys

import lmstudio_mtp as exp
import compare_sql_hybrid_mtp as hybrid

OUT = exp.OUT
report = json.loads((OUT / 'benchmark.json').read_text(encoding='utf-8'))
assert len(report['calls']) == 88, len(report['calls'])
assert report.get('original_restored'), '試験後の元設定を確認する'
cases = {case['name']: case for case in hybrid.make_cases()}
checked = []
for row in report['calls']:
    case = cases[row['case']]
    if case['kind'] == 'rules':
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE facts(id TEXT,consent INT,retest TEXT,submitted INT,withdrawn INT,value INT)')
        db.executemany('INSERT INTO facts VALUES (:id,:consent,:retest,:submitted,:withdrawn,:value)', case['context']['rows'])
        where = "consent=1 AND withdrawn=0 AND " + ("retest='positive' AND submitted=1" if case['name'].endswith('strict')
            else "(retest='positive' OR (retest='negative' AND submitted=1))")
        ids = [x[0] for x in db.execute('SELECT id FROM facts WHERE ' + where + ' ORDER BY id')]
        total = db.execute('SELECT SUM(value) FROM facts WHERE ' + where).fetchone()[0]
        oracle = {'ids': ids, 'total': total}
        db.close()
        assert oracle == row['expected'] == case['expected']
    else:
        import re
        requested = re.findall(r'(?:check-)?ev-\d{4}', case['context']['question'])
        source = {r['evidence_id']: r for r in case['context']['results']}
        oracle = {'records': [{k: source[eid][k] for k in ('evidence_id', 'condition', 'exception', 'value')} for eid in requested]}
        assert oracle == row['expected'] == case['expected']
    raw_text = '\n'.join(x['content'] for x in row['response']['output'] if x['type'] == 'message').strip()
    if raw_text.startswith('```'):
        raw_text = raw_text.split('\n', 1)[1].rsplit('```', 1)[0]
    try:
        parsed = json.loads(raw_text)
        if row['method'] == 'hybrid':
            source_rows = case['context']['results'] if case['kind'] == 'records' else case['context']['rows']
            source = {r['evidence_id'] if case['kind'] == 'records' else r['id']: r for r in source_rows}
            assert len(set(parsed['ids'])) == len(parsed['ids'])
            chosen = [source[eid] for eid in parsed['ids']]
            actual = {'records': [{k: r[k] for k in ('evidence_id', 'condition', 'exception', 'value')} for r in chosen]} if case['kind'] == 'records' else {
                'ids': sorted(parsed['ids']), 'total': sum(r['value'] for r in chosen)}
        else:
            actual = parsed
        exact = actual == oracle
    except (ValueError, KeyError, AssertionError):
        actual, exact = None, False
    assert exact == row['exact'], row
    checked.append(row | {'independent_exact': exact, 'independent_result': actual})

summary = {'measurements': len(checked), 'groups': [], 'extraction_groups': [], 'failures': [],
    'app_version': '0.4.25+1', 'runtime_version': 'llama.cpp CUDA12 2.71.0',
    'gpu_ratio': 0.8, 'context': 16384, 'parallel': 4, 'context_checkpoints': 0,
    'api': 'http://127.0.0.1:1234/api/v1/chat', 'normal_restored_after_benchmark': report['original_restored'],
    'limitations': ['合成資料だけの小標本。実研究の品質、画像・音声、同時4要求は未検証。',
        '推論OFFとON、全文生成とSQL復元を分けて集計。推論ONの出力長は方式間で同じではない。',
        'モデルロードは時間から除外。実行順は通常→MTP3→MTP5→通常で前後対照を保持。',
        'native chat APIにはJSON schema制約を付けていない。以前のllama.cpp構造化出力との正答率を直接比較しない。',
        'cache_prompt=falseを指定できないAPIのため、課題ごとにsystem先頭の識別子を変えた。同一課題の入力は各方式で同一。完全なcold cacheは保証しない。',
        'MTP有効化はロードごとのSDK実採用統計で確認。全測定個別のdraft数はnative chat APIから得られない。']}
for phase in ('normal', 'mtp3', 'mtp5'):
    for method in ('full', 'hybrid'):
        for reasoning in (False, True):
            rows = [r for r in checked if (r['phase'].startswith('normal') if phase == 'normal' else r['phase'] == phase)
                and r['method'] == method and r['reasoning'] == reasoning]
            if not rows:
                continue
            total_tokens = sum(r['stats']['total_output_tokens'] for r in rows)
            generation_seconds = sum(r['stats']['total_output_tokens'] / r['stats']['tokens_per_second'] for r in rows)
            summary['groups'].append({'phase': phase, 'method': method, 'reasoning': reasoning, 'n': len(rows),
                'exact': sum(r['exact'] for r in rows), 'mean_seconds': statistics.mean(r['elapsed_seconds'] for r in rows),
                'median_seconds': statistics.median(r['elapsed_seconds'] for r in rows),
                'tokens_per_second_weighted': total_tokens/generation_seconds,
                'input_tokens_mean': statistics.mean(r['stats']['input_tokens'] for r in rows),
                'ttft_seconds_mean': statistics.mean(r['stats']['time_to_first_token_seconds'] for r in rows)})
            extracts = [r for r in rows if cases[r['case']]['kind'] == 'records']
            if extracts:
                summary['extraction_groups'].append({'phase': phase, 'method': method, 'n': len(extracts),
                    'exact': sum(r['exact'] for r in extracts),
                    'mean_seconds': statistics.mean(r['elapsed_seconds'] for r in extracts),
                    'tokens_per_second_weighted': sum(r['stats']['total_output_tokens'] for r in extracts) /
                        sum(r['stats']['total_output_tokens'] / r['stats']['tokens_per_second'] for r in extracts),
                    'input_tokens_mean': statistics.mean(r['stats']['input_tokens'] for r in extracts)})
for row in checked:
    if not row['exact']:
        summary['failures'].append({k: row.get(k) for k in ('case', 'phase', 'method', 'repeat', 'reasoning', 'parsed', 'expected', 'error')})
for phase in report['conditions']:
    stats = phase['proof_stats']
    if phase['phase'].startswith('mtp'):
        assert stats['totalDraftTokensCount'] > 0 and stats['acceptedDraftTokensCount'] > 0
        assert stats['usedDraftModelKey'] == exp.DRAFT_KEY
    else:
        assert not stats.get('totalDraftTokensCount', 0)
    assert phase['sdk_config']['contextLength'] == 16384
    assert phase['sdk_config']['gpu']['ratio'] == 0.8
summary['load_proofs'] = [{k: r[k] for k in ('phase', 'load_seconds', 'proof_stats')} for r in report['conditions']]
summary['file_sha256'] = {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in ('benchmark.json', 'native-api-probe.json')}
exp.save('summary.json', summary)
exp.save('independent-scoring.json', checked)
print(json.dumps(summary['groups'], ensure_ascii=False, indent=2))

if '--record' in sys.argv:
    installed = json.loads((OUT / 'install.json').read_text(encoding='utf-8'))
    assert installed['proof_stats']['totalDraftTokensCount'] > 0
    assert installed['proof_stats']['acceptedDraftTokensCount'] > 0
    assert not installed.get('error')
    summary['installed_defaults_path'] = installed['defaults_path']
    summary['installed_proof'] = installed['proof_stats']
    installed_checks = json.loads((OUT / 'installed-checks.json').read_text(encoding='utf-8'))
    assert len(installed_checks) == 3 and all(r['exact'] for r in installed_checks)
    summary['installed_checks'] = [{k: r[k] for k in ('case', 'method', 'exact', 'elapsed_seconds', 'stats')} for r in installed_checks]
    summary['selected_draft_tokens'] = 5
    for name, path in [('target', exp.bench.TARGET), ('assistant', Path.home() / '.lmstudio/models' / exp.DRAFT_KEY)]:
        with path.open('rb') as stream:
            summary['file_sha256'][name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert summary['file_sha256']['assistant'] == '25f143b4c15b20cd04216e35e99bd7a56afc6f65e7a4e090a3e20091bb590cbb'
    exp.save('summary.json', summary)
    lines = ['\n\n## 2026-11-10: LM Studio本体で外部MTPを有効化・速度比較\n',
        '- 利用者の「LM Studio版使えるようにして、そのバージョンで速度を検証」に対応。利用者checkoutはkrokharu/transcription-finish-20261102、HEAD d8707f2e02e4e1a74a5d3cb4d6c728e3f5691486。実験コードは開発資料worktreeだけへ追加。既存の未コミット変更、実利用者DB/Vault、Gurumoji runtime、認証設定、本番API接続は変更していない。commit/pushなし。',
        '- 前回の「現行LM Studioは外部Gemma MTP非対応」という判断を訂正。内蔵ヘッド用CLIフラグ --speculative-draft-mtp の拒否は実際に再現したが、外部用のllm.load.llama.speculativeDecoding.draftMtpSidecar経路を見落としていた。公式0.4.22変更履歴にはMTP assistant対応の記載がある。インストール済み0.4.25+1、公式CUDA12 2.71.0のままで動作し、アプリ更新・実行ファイルのパッチ・代理API・外部常駐サーバーは不要だった。',
        '- 専用assistantをlms import --hard-linkでLM Studioのmodelsへ登録。本体は既存google/gemma-4-12b-qatの同じQAT Q4_0。SDK 1.5は新しいロード項目を無視するため、実験プロセス内だけの通信変換でKV load層を追加した。SDK本体やアプリの配布コードは変更していない。実行エンジンの親PIDはLM Studio.exeで、同アプリの1234番API経由で生成したことを資格情報を伏せたprocess証跡に保持した。',
        '- 原設定のGPU0.8/context16384/parallel4を揃え、checkpoint0、temperature0、逐次要求、同じGemma/assistantで比較。通常→MTP3→MTP5→通常の前後対照を取った。ロード時間は除外し別掲。合成7課題×全文/AI選択+一時SQL復元×各2測定×3方式=84測定、条件判定2課題×推論ON×通常/MTP5=4測定、計88測定。warmupとロード証明は別。JSON schema制約のないnative chat APIを使用した。',
        '- 各課題の資料と指示は同じだが、長いprefix再利用を減らすためsystem先頭へ識別子を付与。通常の前後は反復番号0、MTPの反復は0/1。完全なcold cacheは保証しない。全方式で課題別input tokensは一致。過去のb9553/全GPU/context8192/parallel1/構造化出力とは設定・APIが異なるため数値や正答率を直接混ぜない。',
        '', '|方式|本文生成/復元|推論|一致|平均秒|生成tokens/秒|平均入力tokens|', '|---|---|---|---:|---:|---:|---:|']
    for g in summary['groups']:
        lines.append(f"|{g['phase']}|{g['method']}|{'ON' if g['reasoning'] else 'OFF'}|{g['exact']}/{g['n']}|{g['mean_seconds']:.6f}|{g['tokens_per_second_weighted']:.3f}|{g['input_tokens_mean']:.1f}|")
    lines += ['', '- 原文抽出5課題だけの本文生成は、通常9.959884秒/21.165tokens毎秒、MTP3は5.614602秒/47.903tokens毎秒、MTP5は5.370159秒/51.281tokens毎秒。各10/10一致。MTP5のSQL復元方式は1.241888秒/10/10一致だが、これは実験用経路でGurumoji全工程へ組み込んだという意味ではない。',
        '- 原文抽出5課題は3方式それぞれ全文10/10、SQL復元10/10一致。条件判定・整数合計では推論OFFの通常/MTP双方に同じ誤答があり、MTPを品質改善として扱わない。推論ONの全文は通常2/2、MTP5も2/2一致したが小標本。独立採点で生JSONを再parseし、原文と指定ID、および別の一時SQLite WHERE/SUMで期待値を照合した。失敗応答も保存した。',
        '- 先読み5を今回の速度結果から採用。LM Studioのモデル固有既定値 user-concrete-model-default-config/google/gemma-4-12b-qat.json に外部MTPと同じcontext/GPU/parallel設定を保存。原設定の有無/bytesをdefaults-backup.jsonへ保持。追加ロード引数なしのlms loadで再ロードし、実draft提案・採用を再確認してMTP有効のまま引き渡した。元のモデルID・APIポートは継続。rollbackは同スクリプトのrollbackで既定値を元bytesへ戻し、元ロード設定へ復帰する。',
        '- /api/v1/modelsの旧形式speculative_draft_mtp=false/draft_model空欄はsidecar項目を表現しない。MTPの動作判定にはロード層のdraftMtpSidecarと、SDK/OpenAI応答のusedDraftModelKey・totalDraftTokensCount・acceptedDraftTokensCountを使う。各MTPロードと最終再ロードで提案/採用を確認したが、native chat APIの88測定個別のdraft数は取得できない。',
        '- 最終保存後にも原文抽出2件・SQL復元1件の計3応答を追加確認し3/3一致。短い本文抽出3.143980秒、8件の本文抽出11.925359秒、8件のSQL復元3.352947秒で、統制測定より遅い回もあった。初回モデル復帰時のwarmupも38.674tokens毎秒と変動した。同じ実行引数（GPU39層、context16384、parallel4、MTP5）をinstalled-runtime-process.jsonに確認し、再ロード後も同じ速度を常時保証するとは扱わない。',
        '- 実研究の品質・画像/音声・同時4要求・Gurumoji分析全工程は未検証。設定上のparallel4と実同時要求の検証を区別する。アプリ本体コードは今回変更していないため、既存回帰試験は再実行していない。新規2スクリプトの構文確認と生応答の独立再採点を実施した。',
        '- 証跡: 利用者checkoutのoutput/validation/obussql-lmstudio-mtp-20261110/benchmark.json（88測定）、independent-scoring.json、summary.json、install.json、installed-defaults.json、defaults-backup.json、lmstudio-runtime-process.json。実行/復帰: 開発資料scripts/lmstudio_mtp.pyのbenchmark / install --draft-tokens 5 / rollback。',
        '- 一次資料: https://lmstudio.ai/changelog/lmstudio 、https://lmstudio.ai/docs/app/advanced/per-model 、https://lmstudio.ai/docs/app/advanced/speculative-decoding 、https://huggingface.co/ensky0/gemma-4-12B-it-qat-q4_0-gguf-assistant 。']
    note = exp.ROOT / 'output/validation/development-assets-20261016/docs/program-vault/60-Operations/20-Development/gurumoji-improvement-session/02-topics/16-section.md'
    assert lines[0].strip() not in note.read_text(encoding='utf-8')
    with note.open('ab') as stream:
        stream.write(('\n'.join(lines) + '\n').encode('utf-8'))

"""日本語検索と不可逆圧縮をCPUで検証する。合成資料のみを入力する。"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'output/validation/obussql-alternatives-20261110'
sys.path[:0] = [str(ROOT / 'src'), str(OUT / 'deps')]
os.environ['MOJIOKOSI_OBUSSQL_ENABLED'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
import torch
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer
torch.set_num_threads(4)


def save(name, report):
    (OUT / name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def retrieval():
    from gurumoji.services.maf_dev_bridge import FixedEvidenceIndex
    from rank_bm25 import BM25Okapi
    topics = [
        ('停電時は蓄電池で録音を続ける。復電後に転送する。', '停電時の録音', '電気の供給が途絶えた間も音声を残せるか'),
        ('高齢者が質問を聞き取れないときは、話す速さを落として繰り返す。', '高齢者の聞き取り', '年配の人に話の内容が伝わらない場合の対応'),
        ('退会を申し出た参加者の記録は削除する。同意撤回後は再利用しない。', '同意撤回の記録', '参加を取りやめた人のデータを残してよいか'),
        ('深夜の作業は禁止する。ただし救急対応だけは例外とする。', '深夜作業の例外', '夜中に仕事をしてよい特別な状況はあるか'),
        ('薬を飲んだ後に皮膚の赤みが出た場合は服薬を中止し担当医へ連絡する。', '服薬後の皮膚の赤み', '投薬による発疹が疑われた場合に何をするか'),
        ('同意済みでも再検査が陰性なら採用しない。陰性を陽性と扱ってはならない。', '再検査が陰性の採用', '追加検査で異常なしだった人を組み入れてよいか'),
        ('会場が騒がしいときは静かな個室へ移動して聞き取りを行う。', '騒がしい会場', '周囲の雑音で面談を続けられないときの方法'),
        ('資料の未提出者は集計から除く。締切後の提出も対象には戻さない。', '資料未提出者の集計', '必要書類を出さなかった人を後から分析に含めるか'),
        ('画面を見られない利用者には音声による読み上げを提供する。', '画面の読み上げ', '目が不自由な人が表示内容を理解するための支援'),
        ('接続が途切れた間は端末に保存し、通信回復後に同期する。', '通信回復後の同期', 'ネットが使えない間に入力した内容は失われるか'),
        ('録音の再生には本人の許諾が必要。許可のない第三者へ共有しない。', '録音再生の許諾', '声の記録を関係のない人に聞かせてよいか'),
        ('データの欠測をゼロで置き換えない。未回答数を別の列に示す。', '欠測とゼロ', '答えのない項目を数値の零として計算してよいか'),
    ]
    rows = [{'evidence_id': f'synthetic-{i:03}', 'text': text, 'source_revision': 'synthetic-r1'} for i, (text, _, _) in enumerate(topics)]
    distractors = ['施設の入口は午前九時に開く。', '備品は棚に保管する。', '担当者が連絡票を確認する。', '受付後に椅子に座って待つ。']
    rows += [{'evidence_id': f'distractor-{i:03}', 'text': f'架空記録{i}。' + distractors[i % 4], 'source_revision': 'synthetic-r1'} for i in range(120)]
    # 先頭の意味的正解が無得点時の選択で優遇されないよう固定順に入れ替える。
    import random
    random.Random(110).shuffle(rows)
    questions = [{'query': q, 'kind': kind, 'expected': f'synthetic-{i:03}'} for i, (_, direct, para) in enumerate(topics) for kind, q in [('literal', direct), ('paraphrase', para)]]
    questions += [{'query': 'synthetic-005', 'kind': 'exact_id', 'expected': 'synthetic-005'}]
    start = time.perf_counter()
    fixed = FixedEvidenceIndex('alternative-retrieval-synthetic', rows)
    fixed_build = time.perf_counter() - start
    grams = lambda text: [text[i:i+2] for i in range(max(1, len(text)-1))]
    start = time.perf_counter()
    bm25 = BM25Okapi([grams(r['text']) for r in rows])
    bm25_build = time.perf_counter() - start
    start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained('intfloat/multilingual-e5-small', local_files_only=True)
    encoder = AutoModel.from_pretrained('intfloat/multilingual-e5-small', local_files_only=True).eval()
    load_dense = time.perf_counter() - start
    def embed(texts):
        outputs = []
        with torch.inference_mode():
            for offset in range(0, len(texts), 16):
                batch = tokenizer(texts[offset:offset+16], padding=True, truncation=True, max_length=256, return_tensors='pt')
                hidden = encoder(**batch).last_hidden_state.masked_fill(~batch['attention_mask'][..., None].bool(), 0)
                average = hidden.sum(dim=1) / batch['attention_mask'].sum(dim=1)[..., None]
                outputs.append(torch.nn.functional.normalize(average, p=2, dim=1))
        return torch.cat(outputs)
    start = time.perf_counter()
    vectors = embed(['passage: ' + row['text'] for row in rows])
    build_dense = time.perf_counter() - start
    metadata = json.loads((OUT / 'models.json').read_text(encoding='utf-8'))['reranker']
    start = time.perf_counter()
    rerank_tok = AutoTokenizer.from_pretrained(metadata['path'], local_files_only=True)
    reranker = AutoModelForSequenceClassification.from_pretrained(metadata['path'], local_files_only=True).eval()
    load_rerank = time.perf_counter() - start
    report = {'corpus': rows, 'questions': questions, 'measurements': [], 'device': 'cpu,4threads',
              'setup_seconds': {'fixed_index': fixed_build, 'bm25': bm25_build, 'dense_load': load_dense, 'dense_index': build_dense, 'reranker_load': load_rerank},
              'models': {'embedding': 'intfloat/multilingual-e5-small (local cache)', 'reranker': metadata},
              'metrics_scope': '検索順位のみ。解釈品質や実利用者資料の評価ではない。'}
    for question in questions:
        q = question['query']
        times = {}
        start = time.perf_counter()
        selected = fixed.select(rows, q, 3, 30000)
        times['current_literal'] = (time.perf_counter() - start) * 1000
        # 現行は時系列へ並べ直すため、top3集合を評価し、MRRは評価しない。
        current = [r['evidence_id'] for r in selected]
        start = time.perf_counter()
        lexical_scores = bm25.get_scores(grams(q))
        lexical = sorted(range(len(rows)), key=lambda i: -lexical_scores[i])
        times['bm25'] = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        vector = embed(['query: ' + q])
        dense = torch.argsort((vector @ vectors.T)[0], descending=True).tolist()
        times['dense'] = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        rrf = Counter()
        for ranking in (lexical, dense):
            for rank, idx in enumerate(ranking):
                rrf[idx] += 1 / (60 + rank + 1)
        hybrid = sorted(rrf, key=lambda i: -rrf[i])
        rrf_ms = (time.perf_counter() - start) * 1000
        times['hybrid'] = times['bm25'] + times['dense'] + rrf_ms
        start = time.perf_counter()
        pool = hybrid[:10]
        with torch.inference_mode():
            inputs = rerank_tok([(q, rows[i]['text']) for i in pool], padding=True, truncation=True, max_length=256, return_tensors='pt')
            scores = reranker(**inputs).logits.view(-1).tolist()
        reranked = [pool[j] for j in sorted(range(len(pool)), key=lambda j: -scores[j])]
        times['hybrid_rerank'] = times['hybrid'] + (time.perf_counter() - start) * 1000
        ranking_by_name = {'current_literal': current, 'bm25': [rows[i]['evidence_id'] for i in lexical], 'dense': [rows[i]['evidence_id'] for i in dense], 'hybrid': [rows[i]['evidence_id'] for i in hybrid], 'hybrid_rerank': [rows[i]['evidence_id'] for i in reranked]}
        # 原文IDの照合は意味検索の前に確定できるため別の運用候補として測る。
        start = time.perf_counter()
        exact = [i for i, row in enumerate(rows) if row['evidence_id'] == q]
        guard_ms = (time.perf_counter() - start) * 1000
        ranking_by_name['hybrid_rerank_id_guard'] = [rows[i]['evidence_id'] for i in exact] if exact else ranking_by_name['hybrid_rerank']
        times['hybrid_rerank_id_guard'] = guard_ms if exact else times['hybrid_rerank'] + guard_ms
        ranking_by_name['dense_id_guard'] = [rows[i]['evidence_id'] for i in exact] if exact else ranking_by_name['dense']
        times['dense_id_guard'] = guard_ms if exact else times['dense'] + guard_ms
        for method, ranking in ranking_by_name.items():
            report['measurements'].append({'query': q, 'kind': question['kind'], 'method': method,
                'top3': ranking[:3], 'hit3': question['expected'] in ranking[:3],
                'hit1': None if method == 'current_literal' else question['expected'] in ranking[:1], 'elapsed_ms': times[method]})
        save('retrieval.json', report)
    for method in ranking_by_name:
        items = [r for r in report['measurements'] if r['method'] == method]
        print(method, sum(r['hit3'] for r in items), '/', len(items), statistics.median(r['elapsed_ms'] for r in items), flush=True)


def compression():
    from llmlingua import PromptCompressor
    from compare_obussql_external_plans import cases, call, SYSTEM
    metadata = json.loads((OUT / 'models.json').read_text(encoding='utf-8'))['compressor']
    start = time.perf_counter()
    compressor = PromptCompressor(model_name=metadata['path'], device_map='cpu', use_llmlingua2=True,
        model_config={'torch_dtype': torch.float32, 'trust_remote_code': False}, llmlingua2_config={'max_batch_size': 4})
    report = {'model': metadata, 'load_seconds': time.perf_counter()-start, 'device': 'cpu,4threads', 'calls': [], 'lossless': False}
    for held in (False, True):
        for name, context, expected in cases(held):
            source = json.dumps(context['results'], ensure_ascii=False, separators=(',', ':'))
            start = time.perf_counter()
            compressed = compressor.compress_prompt(source, rate=0.5,
                force_tokens=['\n', '。', '、', 'ない', '陰性', '陽性', 'だけ', '未確認'], force_reserve_digit=True)
            elapsed = time.perf_counter() - start
            user = json.dumps({k: v for k, v in context.items() if k != 'results'}, ensure_ascii=False) + '\n圧縮資料:\n' + compressed['compressed_prompt']
            row = call('llmlingua2-off', user, system=SYSTEM)
            row.update(case=('heldout-' if held else 'original-') + name, compress_seconds=elapsed,
                       compression=compressed, exact=row.get('parsed') == {'records': expected},
                       source_target_texts_preserved=all(r[k] in compressed['compressed_prompt'] for r in expected for k in ('evidence_id', 'condition', 'exception')))
            report['calls'].append(row)
            save('compression.json', report)
            print(row['case'], row['exact'], 'compression', elapsed, 'inference', row['elapsed_seconds'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['retrieval', 'compression'])
    globals()[parser.parse_args().mode]()

"""固定発話のSQL取得と、AIが引用したIDからの原文復元。"""
import copy
import hashlib
import json
import re
import sqlite3
import threading
import unicodedata

from ..analysis_core import AnalysisContractError

MODES = frozenset({'sql', 'hybrid'})
VERSION = 'fixed-evidence-sql-v1'


def validate_mode(value):
    if not isinstance(value, str) or value not in MODES:
        raise AnalysisContractError('根拠の取得方式はsqlまたはhybridを指定してください。', field='evidence_mode')
    return value


def search_queries(query):
    """全文と最大7個の検索語を使い、本文の書き換えは行わない。"""
    original = query[:4096]
    normalized = unicodedata.normalize('NFC', original)
    parts = re.split(r'[\s、。！？!?「」『』（）()\[\],:;]+|について|による|によって|した|する|された|される|なら|では|から|まで|[はがをにでとへの]', normalized)
    stop = {'何', '何か', 'どれ', 'どこ', 'なぜ', '事例', '場合', '確認', '教えて', 'ください', 'ある', 'いる', 'か'}
    terms = [s for s in parts if len(s) >= 2 and s not in stop]
    return list(dict.fromkeys([original, *terms]))[:8] if original else []


def _encoded(row):
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


class SqlEvidenceIndex:
    def __init__(self, run_id, rows):
        self.run_id = run_id
        self._lock = threading.RLock()
        self.db = sqlite3.connect(':memory:', check_same_thread=False)
        try:
            self.db.execute('CREATE TABLE evidence(id TEXT PRIMARY KEY,ordinal INTEGER NOT NULL,body TEXT NOT NULL,normalized TEXT NOT NULL,sha256 TEXT NOT NULL)')
            for ordinal, row in enumerate(rows):
                body = _encoded(row)
                self.db.execute('INSERT INTO evidence VALUES (?,?,?,?,?)', (row['evidence_id'], ordinal, body,
                    unicodedata.normalize('NFC', row['text']).casefold(), hashlib.sha256(body.encode()).hexdigest()))
            self.db.commit()
        except Exception:
            self.db.close()
            raise

    def close(self):
        with self._lock:
            self.db.close()

    def _checked(self, rows):
        ids = [row['evidence_id'] for row in rows]
        if len(ids) != len(set(ids)):
            raise AnalysisContractError('固定根拠のIDが重複しています。', code='evidence_missing')
        restored = {}
        for start in range(0, len(ids), 256):
            group = ids[start:start + 256]
            for eid, body, digest in self.db.execute('SELECT id,body,sha256 FROM evidence WHERE id IN (' + ','.join('?' for _ in group) + ')', group):
                if hashlib.sha256(body.encode()).hexdigest() != digest:
                    raise AnalysisContractError('固定根拠のhashが一致しません。', code='evidence_missing')
                restored[eid] = json.loads(body)
        for row in rows:
            original = restored.get(row['evidence_id'])
            # 呼出し側が使う投影項目も全て照合し、本文以外の版違いを通さない。
            if original is None or any(key not in original for key in row) or _encoded({key: original[key] for key in row}) != _encoded(row):
                raise AnalysisContractError('固定根拠の版が一致しません。', code='evidence_missing')
        return restored

    def select(self, rows, query, row_limit, text_limit):
        with self._lock:
            restored = self._checked(rows)
            terms = [unicodedata.normalize('NFC', s).casefold() for s in search_queries(query)]
            scores = {}
            for start in range(0, len(rows), 256):
                ids = [r['evidence_id'] for r in rows[start:start + 256]]
                clauses, parameters = [], []
                for index, term in enumerate(terms):
                    clauses.append('(length(normalized)-length(replace(normalized,?,\'\')))/? * ?')
                    parameters.extend([term, len(term), 1024 if index == 0 else 1])
                score = ' + '.join(clauses) or '0'
                sql = 'SELECT id,(' + score + ') FROM evidence WHERE id IN (' + ','.join('?' for _ in ids) + ')'
                scores.update(self.db.execute(sql, parameters + ids).fetchall())
            order = {r['evidence_id']: i for i, r in enumerate(rows)}
            tokens = set(re.findall(r'[A-Za-z0-9]+(?:[-_:.][A-Za-z0-9]+)*', query[:4096]))
            explicit = set()
            for start in range(0, len(rows), 256):
                ids = [r['evidence_id'] for r in rows[start:start + 256] if r['evidence_id'] in tokens]
                if ids:
                    explicit.update(eid for eid, in self.db.execute('SELECT id FROM evidence WHERE id IN (' + ','.join('?' for _ in ids) + ')', ids))
            ordered = sorted(rows, key=lambda r: (r['evidence_id'] not in explicit, -scores[r['evidence_id']], order[r['evidence_id']]))
            chosen, size = set(), 0
            for row in ordered:
                if len(chosen) >= row_limit:
                    break
                if size + len(row['text']) <= text_limit:
                    chosen.add(row['evidence_id'])
                    size += len(row['text'])
            return [{key: copy.deepcopy(restored[r['evidence_id']][key]) for key in r}
                for r in rows if r['evidence_id'] in chosen]


def select_rows(rows, query, row_limit, text_limit):
    index = SqlEvidenceIndex('', rows)
    try:
        return index.select(rows, query, row_limit, text_limit)
    finally:
        index.close()


def resolve_citations(rows, response, *, allowed_ids, dataset_version, row_limit=120, text_limit=60000):
    """AIの引用IDだけを受け付け、本文と数値は固定SQLから取得する。"""
    ids = []
    def visit(value):
        if isinstance(value, dict):
            refs = value.get('evidence_ids', [])
            if not isinstance(refs, list) or any(not isinstance(eid, str) for eid in refs):
                raise AnalysisContractError('根拠IDの形式が正しくありません。', code='evidence_missing')
            ids.extend(refs)
            for key, child in value.items():
                if key != 'evidence_ids':
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    # 追加分析の依頼IDは将来読む範囲であり、今回の引用には含めない。
    for field in ('claims', 'issues', 'label_patches', 'label_definitions', 'label_requirements', 'claim_verdicts'):
        visit(response.get(field, []))
    wanted = list(dict.fromkeys(ids))
    if any(eid not in allowed_ids for eid in wanted):
        raise AnalysisContractError('提示されていない根拠は復元できません。', code='evidence_not_provided')
    candidates = [r for r in rows if r['evidence_id'] in wanted]
    if {r['evidence_id'] for r in candidates} != set(wanted):
        raise AnalysisContractError('引用された固定根拠がありません。', code='evidence_missing')
    if len(candidates) > row_limit or sum(len(r['text']) for r in candidates) > text_limit:
        raise AnalysisContractError('引用原文の復元上限を超えています。', code='evidence_resolution_limit')
    sources = select_rows(candidates, '', len(candidates), text_limit)
    return {'version': VERSION, 'mode': 'hybrid', 'dataset_version': dataset_version,
        'selection': 'ai_citation_ids', 'sources': sources,
        'sources_sha256': hashlib.sha256(_encoded(sources).encode()).hexdigest()}

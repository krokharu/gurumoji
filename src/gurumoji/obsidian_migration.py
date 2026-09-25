"""Backed-up, resumable migration of legacy Vault paths and database references."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import closing
from pathlib import Path

from .vault_files import safe_path, write_atomic
from .obsidian_layout import ObsidianLayout, HOME, unpack, pack
from .vault_note_policy import NoteWrite, append_change


def rewrite_links(text: str, mapping: dict[str, str]) -> str:
    targets = {k.removesuffix('.md'): v.removesuffix('.md') for k, v in mapping.items()}
    def replace(match):
        value = match[1]
        path, mark, suffix = re.split(r'([#|])', value, maxsplit=1) if re.search(r'[#|]', value) else (value, '', '')
        found = targets.get(path.removesuffix('.md'))
        return '[[' + (found + mark + suffix if found else value) + ']]'
    # Literal transcript quotations and fenced legacy transcript blocks are immutable.
    result, fence = [], None
    for line in text.splitlines(keepends=True):
        opening = re.match(r'^\s*(`{3,}|~{3,})', line)
        if opening:
            if fence is None: fence = opening[1]
            elif opening[1][0] == fence[0] and len(opening[1]) >= len(fence): fence = None
            result.append(line)
        elif fence or line.startswith('>'):
            result.append(line)
        else:
            result.append(re.sub(r'(?<!\\)\[\[([^\]]+)\]\]', replace, line))
    return ''.join(result)


LEGACY_FOLDERS = ('15-Finishing', '20-Conversations', '25-Sources', '40-Analyses', '95-Indexes')


def _plan_mapping(layout: ObsidianLayout, states: list[Path]) -> tuple[dict[str, str], dict[str, str]]:
    """Decide the new path of every legacy note; reads the Vault, writes only the registry."""
    mapping, ownership = {}, {}
    # Current states also identify older finishing notes without properties.
    finishing = {}
    for state_path in states:
        state = json.loads(state_path.read_text(encoding='utf-8'))
        state.setdefault('status_note', state['folder'] + '/状態.md')
        record = layout.register(state['item_id'], state['title'])
        for path in safe_path(layout.vault, state['folder']).rglob('*.md'):
            relative = path.relative_to(layout.vault).as_posix()
            finishing[relative] = (state, record)
    for path in sorted(layout.vault.rglob('*.md')):
        relative = path.relative_to(layout.vault).as_posix()
        if relative.startswith('.obsidian/'): continue
        props, _ = unpack(path.read_text(encoding='utf-8-sig'))
        item_id = props.get('conversation_id')
        title = str(props.get('title') or item_id or path.stem)
        if item_id: record = layout.register(str(item_id), title)
        target = relative
        if relative in finishing:
            state, record = finishing[relative]
            item_id = state['item_id']
            roles = {'work': '全文', 'outline': 'アウトライン', 'control': '操作',
                     'status_note': '状態', 'original_note': '保存原文'}
            role = next((label for k, label in roles.items() if state.get(k) == relative), None)
            target = f"{record['folder']}/{record['code']}-{role}.md" if role else f"{record['folder']}/履歴/仕上げ/{record['code']}-{path.name}"
        elif relative.startswith('25-Sources/') and item_id:
            target = layout.source_dir(str(item_id), title, props['input_snapshot_id']) + '/' + path.name
        elif relative.startswith('40-Analyses/') and item_id:
            target = layout.analysis_dir(str(item_id), title, props['analysis_id']) + '/' + path.name
        elif relative.startswith('20-Conversations/') and item_id:
            target = layout.note_path(str(item_id), title, '分析まとめ')
        else:
            prefixes = {'10-Projects/': '40-研究/プロジェクト/', '15-Finishing/': '90-運用/旧仕上げ/',
                        '20-Conversations/': '90-運用/旧会話案内/', '25-Sources/': '90-運用/原文案内/',
                        '30-Speakers/': '30-人物/', '40-Analyses/': '90-運用/分析案内/',
                        '45-Methods/': '90-運用/手法/', '50-Codes/': '40-研究/コード/',
                        '60-ResearchNotes/': '40-研究/メモ/', '70-Concepts/': '40-研究/概念/',
                        '80-Attachments/': '80-添付/', '90-Templates/': '90-運用/テンプレート/',
                        '95-Indexes/': '90-運用/'}
            for old, new in prefixes.items():
                if relative.startswith(old): target = new + relative[len(old):]; break
            if relative == '00-Home.md': target = '90-運用/以前のホーム.md'
        mapping[relative] = target
        ownership[relative] = str(item_id) if item_id else ''
    # Preserve non-Markdown attachments in old folders too.
    for path in layout.vault.rglob('*'):
        relative = path.relative_to(layout.vault).as_posix()
        if path.is_file() and relative.startswith('80-Attachments/'):
            mapping[relative] = '80-添付/' + relative[len('80-Attachments/'):]
    if len(set(mapping.values())) != len(mapping): raise ValueError('移行先の名前が重複しています。')
    return mapping, ownership


def _running_states(layout: ObsidianLayout) -> list[Path]:
    states = list((layout.data / 'obsidian_workbench').glob('*/state.json'))
    for path in states:
        if json.loads(path.read_text(encoding='utf-8')).get('status') == 'running':
            raise ValueError('AI仕上げの処理が終了してから移行してください。')
    return states


def plan_migration(database_file: Path) -> dict:
    """Dry run (OBS-16): list what migrate would move, rewrite and refuse, without writing anything.

    Interview codes are assigned on a throwaway copy of the registry, so the
    counts match a later migrate unless the Vault changes in between.
    """
    database_file = Path(database_file).resolve()
    layout = ObsidianLayout(database_file)
    control = layout.data / 'obsidian_layout'
    if (control / 'migration-v1.json').exists():
        return {'version': 1, 'needed': False, 'reason': '移行済みです。'}
    if (control / 'migration-pending.json').exists():
        pending = json.loads((control / 'migration-pending.json').read_text(encoding='utf-8'))
        return {'version': 1, 'needed': True, 'reason': '中断した移行があります。次の起動で同じバックアップから再開します。',
                'moves': sum(k != v for k, v in pending['mapping'].items())}
    if not any((layout.vault / name).exists() for name in LEGACY_FOLDERS):
        return {'version': 1, 'needed': False, 'reason': '旧形式のフォルダーはありません。'}
    states = _running_states(layout)
    with tempfile.TemporaryDirectory(prefix='gurumoji-migration-plan-') as scratch:
        registry = Path(scratch) / 'interviews.json'
        if layout.registry.exists(): shutil.copy2(layout.registry, registry)
        layout.registry = registry
        layout.note_log = Path(scratch) / 'note_changes.jsonl'
        mapping, _ = _plan_mapping(layout, states)
    moves = {old: new for old, new in mapping.items() if old != new}
    # migrate stops when one of these holds different content; identical files are accepted.
    existing = sorted(new for new in moves.values() if safe_path(layout.vault, new).exists())
    links = 0
    for old in mapping:
        if old.endswith('.md'):
            text = safe_path(layout.vault, old).read_text(encoding='utf-8-sig')
            links += rewrite_links(text, mapping) != text
    return {'version': 1, 'needed': True, 'notes': len(mapping), 'moves': len(moves),
            'unchanged': len(mapping) - len(moves), 'link_rewrites': links,
            'existing_targets': existing, 'mapping': mapping,
            'backup': '移行前に obsidian_layout/backup-* へVault・作業台・analysis_store・台帳・DBを写します。'}


def migrate(database_file: Path) -> dict:
    database_file = Path(database_file).resolve()
    layout = ObsidianLayout(database_file)
    control = layout.data / 'obsidian_layout'
    done = control / 'migration-v1.json'
    pending = control / 'migration-pending.json'
    if done.exists():
        return json.loads(done.read_text(encoding='utf-8'))
    if not pending.exists() and not any((layout.vault / name).exists() for name in LEGACY_FOLDERS):
        return {'version': 1, 'moved': 0, 'interviews': len(layout.load()['interviews'])}
    states = _running_states(layout)
    if pending.exists():
        plan = json.loads(pending.read_text(encoding='utf-8'))
    else:
        backup = control / ('backup-' + uuid.uuid4().hex)
        backup.mkdir(parents=True)
        if layout.vault.exists(): shutil.copytree(layout.vault, backup / 'vault')
        for name in ('obsidian_workbench', 'analysis_store'):
            source = layout.data / name
            if source.exists(): shutil.copytree(source, backup / name)
        if layout.registry.exists(): shutil.copy2(layout.registry, backup / 'interviews.json')
        if database_file.exists():
            with closing(sqlite3.connect(database_file)) as source, closing(sqlite3.connect(backup / 'library.sqlite3')) as target:
                source.backup(target)
        mapping, ownership = _plan_mapping(layout, states)
        plan = {'backup': str(backup), 'mapping': mapping, 'ownership': ownership}
        write_atomic(pending, json.dumps(plan, ensure_ascii=False, indent=2).encode())
    backup = Path(plan['backup'])
    if not backup.resolve().is_relative_to(control.resolve()): raise ValueError('バックアップの場所が不正です。')
    mapping = plan['mapping']
    hashes = {}
    # Always derive the migration from the immutable backup, including after a crash.
    for old, new in mapping.items():
        original = safe_path(backup / 'vault', old).read_bytes()
        content = original
        if old.endswith('.md'):
            text = rewrite_links(original.decode('utf-8-sig'), mapping)
            item_id = plan['ownership'].get(old)
            if item_id:
                kind = 'analysis' if new.endswith('-分析まとめ.md') else 'transcript' if new.endswith('-全文.md') else 'outline' if new.endswith('-アウトライン.md') else 'support'
                scope = 'detail' if kind in {'analysis', 'transcript', 'outline'} else 'history' if '/履歴/' in new else 'support'
                text = layout.decorate(text, item_id, kind, scope)
            else:
                props, body = unpack(text)
                tags = props.get('tags') or []
                if isinstance(tags, str): tags = tags.split()
                props['tags'] = list(dict.fromkeys(tags + ['graph/support']))
                text = pack(props, body)
            content = text.encode()
        target = safe_path(layout.vault, new)
        source = safe_path(layout.vault, old)
        if source.exists() and source.read_bytes() not in (original, content):
            raise ValueError('移行中にノートが編集されました。バックアップと編集内容を保持して中断しました。')
        if target.exists() and target != source and target.read_bytes() != content:
            raise ValueError('移行先に別の内容があります。既存内容を保持して中断しました。')
        write_atomic(target, content)
        hashes[old] = (hashlib.sha256(original).hexdigest(), hashlib.sha256(content).hexdigest())
        # A resumed migration logs the same move again; the log is a record, not a ledger (OBS-15).
        append_change(layout.note_log, 'research', NoteWrite('migrated', new, hashes[old][1], hashes[old][0], source=old))
    if database_file.exists():
        with closing(sqlite3.connect(database_file)) as conn, conn:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'obsidian_notes' in tables:
                for old, new in mapping.items():
                    row = conn.execute('SELECT sha256 FROM obsidian_notes WHERE path=?', (old,)).fetchone()
                    if row:
                        before, after = hashes[old]
                        # A pre-existing human edit stays a conflict on future publication.
                        conn.execute('UPDATE obsidian_notes SET path=?,sha256=? WHERE path=?',
                                     (new, after if row[0] == before else row[0], old))
            if 'analysis_runs' in tables:
                for old, new in mapping.items():
                    conn.execute('UPDATE analysis_runs SET note_path=? WHERE note_path=?', (new, old))
    source_workbench = backup / 'obsidian_workbench'
    for old in source_workbench.glob('*/*.json'):
        if not (old.name.startswith('state') or old.name.startswith('result-')): continue
        data = json.loads(old.read_text(encoding='utf-8'))
        migrated = dict(data)
        if old.name.startswith('state') and 'status_note' not in migrated:
            status_path = data.get('folder', '') + '/状態.md'
            if status_path in mapping: migrated['status_note'] = mapping[status_path]
        for key in ('work', 'outline', 'control', 'original_note', 'status_note', 'result_note', 'final_outline_note'):
            if key in data: migrated[key] = mapping.get(data[key], data[key])
        for key in ('note_ids', 'sources'):
            if key in data: migrated[key] = {mapping.get(k, k): v for k, v in data[key].items()}
        if old.name.startswith('state') and migrated.get('work'):
            migrated['folder'] = str(Path(migrated['work']).parent).replace('\\', '/')
        for relative, expected in data.get('sources', {}).items():
            if isinstance(expected, str) and relative in hashes and expected == hashes[relative][0]:
                migrated['sources'][mapping[relative]] = hashes[relative][1]
        target = safe_path(layout.data / 'obsidian_workbench', old.relative_to(source_workbench).as_posix())
        write_atomic(target, json.dumps(migrated, ensure_ascii=False).encode())
    # Delete only unchanged originals inside the checked Vault, after backup and catalog update.
    for old, new in mapping.items():
        if old == new: continue
        source = safe_path(layout.vault, old)
        if source.exists():
            expected = safe_path(backup / 'vault', old).read_bytes()
            if source.read_bytes() != expected: raise ValueError('移行元が編集されたため、そのファイルを保持しました。')
            source.unlink()
    # Remove only the folders this migration emptied; the researcher's own empty folders stay (OBS-13).
    emptied = {parent for old, new in mapping.items() if old != new
               for parent in Path(old).parents if parent != Path('.')}
    for relative in sorted(emptied, key=lambda p: len(p.parts), reverse=True):
        path = safe_path(layout.vault, relative.as_posix())
        if path.is_dir() and not path.is_symlink() and not any(path.iterdir()):
            path.rmdir()
    layout.publish_navigation()
    for path in (layout.data / 'obsidian_workbench').glob('*/state.json'):
        layout.sync_finishing(json.loads(path.read_text(encoding='utf-8')))
    # Existing saved analyses may exist without a finishing workbench.
    for item_id, record in layout.load()['interviews'].items():
        summary = layout.note_path(item_id, record['title'], '分析まとめ')
        if safe_path(layout.vault, summary).exists(): layout.update(item_id, record['title'], {'analysis': summary})
    report = {'version': 1, 'backup': str(backup), 'moved': sum(k != v for k, v in mapping.items()),
              'interviews': len(layout.load()['interviews']), 'mapping': mapping}
    write_atomic(done, json.dumps(report, ensure_ascii=False, indent=2).encode())
    pending.unlink(missing_ok=True)
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='旧形式ResearchVaultの移行計画を表示します（何も書き換えません）。')
    parser.add_argument('database', type=Path, help='ライブラリのデータベース（例：runtime/data/library.sqlite3）')
    print(json.dumps(plan_migration(parser.parse_args().database), ensure_ascii=False, indent=2))

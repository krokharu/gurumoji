"""Build the derived ID/path/hash catalogue without reading it as AI context."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import yaml

FRONT=re.compile(r'\A\ufeff?---[^\S\n]*\r?\n(.*?)\r?\n---[^\S\n]*(?:\r?\n|$)',re.S)

def build_catalog(root: Path):
    notes=[];seen={}
    for p in sorted(root.rglob('*.md')):
        if any(x.startswith('.') for x in p.relative_to(root).parts):continue
        data=p.read_bytes();text=data.decode('utf-8-sig');m=FRONT.match(text)
        meta=yaml.safe_load(m[1]) or {} if m else {}
        note_id=meta.get('note_id')
        if not note_id:raise ValueError(f'Missing note_id: {p.relative_to(root)}')
        if note_id in seen:raise ValueError(f'Duplicate note_id: {note_id}')
        seen[note_id]=p
        notes.append({'path':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(data).hexdigest(),
            'chars':len(text),'metadata':meta})
    return json.loads(json.dumps({'schema_version':1,'authority':'derived-index; Markdown and code remain authoritative','notes':notes},ensure_ascii=False,default=str))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault',type=Path,default=Path(__file__).resolve().parents[1]/'docs/program-vault')
    parser.add_argument('--check',action='store_true');args=parser.parse_args()
    catalog=build_catalog(args.vault);p=args.vault/'00-Catalog.json'
    if args.check:
        if not p.exists() or json.loads(p.read_text(encoding='utf-8'))!=catalog:
            raise SystemExit('Catalogue stale: regenerate with scripts/build_program_vault_catalog.py')
        print(f'Catalogue current: {len(catalog["notes"])} notes')
    else:
        p.write_text(json.dumps(catalog,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
        print(f'Catalogued {len(catalog["notes"])} notes')

if __name__=='__main__':main()

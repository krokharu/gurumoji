"""Validate Software Vault IDs, catalogue, files, anchors and index reachability."""
from __future__ import annotations
import argparse
from collections import defaultdict, deque
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from build_program_vault_catalog import build_catalog
from restructure_program_vault import file_inventory, parse, heading_spans, resolve_wiki, WIKI, MDLINK, slug, plain_heading

def prose(body):
    fence=None
    for line in body.splitlines():
        marker=re.match(r'^\s*(`{3,}|~{3,})',line)
        if marker:
            if fence is None:fence=marker[1][0]
            elif fence==marker[1][0]:fence=None
            continue
        if fence is None:yield re.sub(r'(`+).*?\1',lambda m:'' if '[[' in m[0] or '](' in m[0] else m[0],line)

def check(root: Path,virtual_root: Path|None=None):
    root=root.resolve();virtual_root=(virtual_root or root).resolve()
    files=file_inventory(root);notes={n:parse(d) for n,d in files.items() if n.endswith('.md')}
    errors=[];edges=defaultdict(set);link_count=0;anchor_count=0;ids={}
    for name,(meta,body) in notes.items():
        for field in ['note_id','note_type','title','status','tags']:
            if not meta.get(field):errors.append(f'{name}: missing {field}')
        note_id=meta.get('note_id')
        if note_id in ids:errors.append(f'duplicate note_id {note_id}: {name}')
        ids[note_id]=name
        for line in prose(body):
            targets=[]
            for m in WIKI.finditer(line):
                target=m[1].split('|',1)[0].rstrip('\\');namepart,_,fragment=target.partition('#')
                resolved=resolve_wiki(root,name,namepart,files)
                targets.append((m[0],resolved,fragment,'wiki'))
            for m in MDLINK.finditer(line):
                raw=m[1].strip('<>');parsed=urlsplit(raw)
                if parsed.scheme or raw.startswith('//'):continue
                path=((virtual_root/name).parent/unquote(parsed.path)).resolve() if parsed.path else virtual_root/name
                if path.is_relative_to(virtual_root):
                    resolved=path.relative_to(virtual_root).as_posix()
                else:
                    resolved=str(path) if path.is_file() else None
                targets.append((m[0],resolved,unquote(parsed.fragment),'markdown'))
            for text,target,fragment,kind in targets:
                link_count+=1
                if target is None or (not Path(target).is_absolute() and target not in files):
                    errors.append(f'{name}: missing target {text}');continue
                if target in notes:
                    edges[name].add(target)
                    if fragment:
                        anchor_count+=1
                        target_body=notes[target][1]
                        headings=[h for _,_,h in heading_spans(target_body)]
                        all_headings=headings+[plain_heading(h) for h in headings]
                        valid=fragment in all_headings if kind=='wiki' else fragment in [slug(h) for h in all_headings]
                        if fragment.startswith('^'):valid=fragment in target_body
                        if not valid:errors.append(f'{name}: missing anchor {text}')
    queue=deque(n for n in ['00-Home.md','00-Index.md','00-AI-Entry.md'] if n in notes);reached=set(queue)
    while queue:
        for target in edges[queue.popleft()]:
            if target not in reached:reached.add(target);queue.append(target)
    excluded=[n for n,(m,_) in notes.items() if m.get('note_type')=='path-redirect' or n.startswith('99-Archive/')]
    orphaned=sorted(set(notes)-reached-set(excluded))
    errors.extend('unreachable from entry: '+n for n in orphaned)
    if '00-Catalog.json' in files:
        if json.loads(files['00-Catalog.json'])!=build_catalog(root):errors.append('00-Catalog.json is stale')
    result={'notes':len(notes),'content_notes':len(notes)-len(excluded),'legacy_redirects':len(excluded),
        'links_checked':link_count,'note_anchors_checked':anchor_count,'unreachable':orphaned,'errors':errors}
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault',type=Path,default=Path(__file__).resolve().parents[1]/'docs/program-vault')
    parser.add_argument('--virtual-root',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=check(args.vault,args.virtual_root)
    rendered=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    print(rendered,end='')
    if args.output:args.output.write_text(rendered,encoding='utf-8')
    raise SystemExit(bool(result['errors']))

if __name__=='__main__':main()

"""Stage, validate, apply or restore a lossless Software Vault reorganisation.

Only Markdown and the derived 00-Catalog.json are changed. App data, Obsidian
settings, non-Markdown evidence/assets and machine-read expert notes stay put.
Plan in a separate directory first; apply/restore refuse concurrent edits.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile

import yaml

VERSION = 1
DATE = '2026-10-11'
LIMIT = 7000
FRONT = re.compile(r'\A\ufeff?---[^\S\n]*\n(.*?)\n---[^\S\n]*(?:\n|$)', re.S)
WIKI = re.compile(r'(?<!\\)\[\[([^\]\n]+)\]\]')
MDLINK = re.compile(r'\[[^\]\n]*\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"]*")?\)')

# Real content goes into responsibility folders; old paths remain redirects.
GROUPS = {
 '10-Architecture': {'10-System': ('システム構成', 'overview system-map')},
 '20-Modules': {
  '10-Inventory': ('機能・モジュール一覧', 'feature-inventory module-map'),
  '20-Analysis': ('分析実行', 'analysis-orchestration'),
  '30-Storage': ('Obsidian連携', 'obsidian-integration'),
  '40-Interface': ('画面とURL', 'ui-screens')},
 '30-Data': {
  '10-Inventory': ('保存先の全体像', 'current-storage'),
  '20-Analysis': ('固定分析の保存', 'analysis-storage-v1'),
  '30-Transcript': ('文字起こしの準備', 'transcript-preparation-v1'),
  '40-Vaults': ('Vault間の保存契約', 'four-vaults-v1')},
 '40-Design': {
  '10-Analysis': ('分析コア・実行設計', 'core-handler-routing-reorganization-plan quantification-statistics-plan analysis-milestone-visualization-design analysis-execution-ux-plan analysis-history-viewer conversation-analysis-extension-plan analysis-core-state-alignment-plan'),
  '20-Knowledge': ('専門知識・モデル・作業記憶', 'expert-knowledge-production-plan expert-knowledge-production-execution-report a100-knowledge-control-plane-plan model-context-and-work-memory-plan'),
  '30-Interface': ('UI設計と調査', 'ui-design-knowledge ui-design-contract ui-design-implementation-plan ui-microcopy-state-catalog ui-ux-issues video-ui-redesign-plan'),
  '40-Storage': ('Obsidian・同期・正本', 'obsidian-plan obsidian-graph-plan storage-policy sync-contract'),
  '50-Governance': ('判断・課題・開発規約', 'decisions convergence-plan known-issues ai-development-rules program-vault-rules method-rules'),
  '60-Output': ('スライド出力', 'slide-generation-design-and-prompts')},
 '50-Tests': {
  '10-Storage': ('保存・Obsidianの検証', 'obsidian-safety-test-plan'),
  '20-Analysis': ('分析・専門家の検証', 'ai-insights-reference-checklist method-expert-sample-verification'),
  '30-Interface': ('UIシナリオと受入', 'ui-design-scenarios ui-design-acceptance')},
 '60-Operations': {
  '10-Data': ('バックアップと復元', 'backup-restore'),
  '20-Development': ('開発と引継ぎ', 'dot-cloud-development-handoff gurumoji-department-briefs gurumoji-improvement-session')},
 '70-Changes': {'10-Compatibility': ('構造変更と互換性', 'app-py-phase5')},
 '90-Templates': {
  '10-Analysis': ('手法・分析結果', 'method-registration research-result'),
  '20-Research': ('研究メモ・調査記録', 'research-memo research-log'),
  '30-Knowledge': ('専門家・文献', 'expert-definition literature-note')},
}
DOMAIN_TITLES = {'10-Architecture':'構成', '20-Modules':'機能・責務', '30-Data':'データ契約',
 '40-Design':'設計・判断', '50-Analysis-Methods':'手法・専門家・文献', '50-Tests':'検証',
 '60-Operations':'運用', '70-Changes':'変更と互換性', '90-Templates':'記入テンプレート'}

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def parse(data: bytes):
    text = data.decode('utf-8-sig').replace('\r\n','\n')
    m = FRONT.match(text)
    return (yaml.safe_load(m[1]) or {}, text[m.end():]) if m else ({}, text)

def pack(meta: dict, body: str) -> bytes:
    return ('---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=140).rstrip()
            + '\n---\n\n' + body.strip() + '\n').encode('utf-8')

def heading_spans(body: str):
    """Return real headings, retaining byte-for-byte body slices between them."""
    result, offset, fence = [], 0, None
    for line in body.splitlines(keepends=True):
        marker = re.match(r'^\s*(`{3,}|~{3,})',line)
        if marker:
            if fence is None:
                fence = marker[1][0]
            elif fence == marker[1][0]:
                fence = None
        elif fence is None:
            m = re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$',line)
            if m:
                result.append((offset,len(m[1]),m[2]))
        offset += len(line)
    return result

def split_body(body: str, limit: int = LIMIT):
    """Split at heading boundaries, never inside tables, code, or paragraphs."""
    headings = heading_spans(body)
    boundaries = [0, *[p for p,l,_ in headings if l==2 and p>0], len(body)]
    boundaries = sorted(set(boundaries))
    chunks = []
    def split(start,end):
        if end-start > limit:
            candidates = [(p,l) for p,l,_ in headings if start<p<end and l>=3]
            if candidates:
                level = min(l for _,l in candidates)
                positions = [start,*[p for p,l in candidates if l==level],end]
                for a,b in zip(positions,positions[1:]):
                    split(a,b)
                return
            # Wide catalogues may be one table with no subheadings. Split at
            # whole rows only; the display header is repeated separately.
            position=start;cuts=[start];fence=None
            for line in body[start:end].splitlines(keepends=True):
                marker=re.match(r'^\s*(`{3,}|~{3,})',line)
                if marker:
                    if fence is None:fence=marker[1][0]
                    elif fence==marker[1][0]:fence=None
                if fence is None and line.lstrip().startswith('|') and position-cuts[-1]>=limit-800:
                    cuts.append(position)
                position+=len(line)
            if len(cuts)>1:
                for a,b in zip(cuts,[*cuts[1:],end]):
                    if body[a:b].strip():chunks.append((a,b,body[a:b]))
                return
        if body[start:end].strip():
            chunks.append((start,end,body[start:end]))
    for a,b in zip(boundaries,boundaries[1:]):
        split(a,b)
    # Merge adjacent small blocks, up to the budget; sections keep their headings.
    merged = []
    for start,end,part in chunks:
        if merged and len(merged[-1][2])+len(part)<=limit and len(merged[-1][2])<1200:
            a,_,previous=merged.pop()
            merged.append((a,end,previous+part))
        else:
            merged.append((start,end,part))
    assert ''.join(p for _,_,p in merged).strip()==body.strip(), 'body lost during split'
    return merged

def title_for(body: str, fallback: str) -> str:
    headings=heading_spans(body)
    if headings:return headings[0][2]
    first=body.strip().splitlines()[0] if body.strip() else ''
    if first.startswith('|'):
        return '表：'+plain_heading(re.split(r'(?<!\\)\|',first.strip('| '),maxsplit=1)[0].strip())[:80]
    return fallback

def table_header(body: str,start: int,part: str) -> str:
    if not part.lstrip().startswith('|'):return ''
    lines=body[:start].splitlines()
    for i in range(len(lines)-1,0,-1):
        if re.match(r'^\s*\|\s*:?-{3,}',lines[i]):
            return lines[i-1]+'\n'+lines[i]+'\n'
        if not lines[i].lstrip().startswith('|') and lines[i].strip():break
    return ''

def slug(text: str) -> str:
    return re.sub(r'[^\w\- ]','',text.lower()).replace(' ','-')

def plain_heading(text: str) -> str:
    def label(m):
        value=m[1]
        if '|' in value:return value.split('|',1)[1]
        return value.rsplit('/',1)[-1]
    text=WIKI.sub(label,text)
    text=re.sub(r'\[([^]]+)\]\([^)]*\)',r'\1',text)
    return re.sub(r'[`*_]','',text).replace('\\|','|')

def file_inventory(root: Path) -> dict[str,bytes]:
    return {p.relative_to(root).as_posix():p.read_bytes() for p in sorted(root.rglob('*'))
            if p.is_file() and not any(x.startswith('.') for x in p.relative_to(root).parts)}

def resolve_wiki(root: Path, origin: str, target: str, files: dict):
    if not target:
        return origin
    target=unquote(target)
    variants=[target] if Path(target).suffix else [target+'.md',target]
    for base in [root,(root/origin).parent]:
        for v in variants:
            q=(base/v).resolve()
            if q.is_relative_to(root) and q.relative_to(root).as_posix() in files:
                return q.relative_to(root).as_posix()
    candidates=[p for p in files if any(p==v or p.endswith('/'+v) for v in variants)]
    return candidates[0] if len(candidates)==1 else None

def rewrite_links(body: str, origin: str, destination: str, root: Path, files: dict,
                  moves: dict, anchors: dict) -> str:
    """Relocate prose links; fenced/inline examples remain literal."""
    def destination_for(old,fragment):
        return anchors.get((old,unquote(fragment)),moves.get(old,old)) if fragment else moves.get(old,old)
    def wiki(m):
        text=m[1]
        before,sep,alias=text.partition('|')
        escaped=before.endswith('\\') and bool(sep)
        before=before.rstrip('\\') if escaped else before
        name,hashmark,fragment=before.partition('#')
        old=resolve_wiki(root,origin,name,files)
        if old is None:
            return m[0]
        new=destination_for(old,fragment)
        # Normalise to full Vault paths so repeated 00-Index names are safe.
        new=new[:-3] if new.endswith('.md') else new
        if not sep and moves.get(old,old)!=old:
            alias=name.rsplit('/',1)[-1]+(hashmark+fragment if hashmark else '')
            sep='|';escaped=line.lstrip().startswith('|')
        return '[['+new+(hashmark+fragment if hashmark else '')+('\\' if escaped else '')+(sep+alias if sep else '')+']]'
    def markdown(m):
        raw=m[1].strip('<>')
        parsed=urlsplit(raw)
        if parsed.scheme or raw.startswith('//'):
            return m[0]
        old_absolute=((root/origin).parent/unquote(parsed.path)).resolve() if parsed.path else (root/origin)
        if old_absolute.is_relative_to(root):
            old=old_absolute.relative_to(root).as_posix()
            if old not in files:
                return m[0]
            target=root/destination_for(old,parsed.fragment)
        else:
            target=old_absolute
        relative=os.path.relpath(target,(root/destination).parent).replace('\\','/')
        new=relative+('?' + parsed.query if parsed.query else '')+('#'+parsed.fragment if parsed.fragment else '')
        if ' ' in new or m[1].startswith('<'):
            new='<'+new+'>'
        return m[0][:m.start(1)-m.start()]+new+m[0][m.end(1)-m.start():]
    output,fence=[],None
    for line in body.splitlines(keepends=True):
        marker=re.match(r'^\s*(`{3,}|~{3,})',line)
        if marker:
            if fence is None: fence=marker[1][0]
            elif fence==marker[1][0]: fence=None
        elif fence is None:
            # Protect inline code. Do not rewrite raw code paths or examples.
            pieces=re.split(r'(`+[^`\n]*`+)',line)
            for i in range(0,len(pieces),2):
                pieces[i]=MDLINK.sub(markdown,WIKI.sub(wiki,pieces[i]))
            line=''.join(pieces)
        output.append(line)
    return ''.join(output)

def small_index(note_id,title,rows,summary=None):
    meta={'note_id':note_id,'note_type':'retrieval-index','title':title,
          'summary':summary or f'{title}の目的別入口。必要な責務を一つ選び、詳細へ進む。',
          'status':'current','updated':DATE,'tags':['gurumoji/program','gurumoji/retrieval']}
    body=f'# {title}\n\n必要な項目だけを選び、本文は選んだノートで読む。\n\n'
    body+='\n'.join(f'- [[{p[:-3]}|{plain_heading(t)}]] — {s}' for p,t,s in rows)
    return pack(meta,body)

def stage(vault: Path, work: Path):
    vault=vault.resolve();work=work.resolve()
    if work==vault or work.is_relative_to(vault):
        raise ValueError('Plan directory must be outside the Vault')
    if work.exists() and any(work.iterdir()):
        raise ValueError('Use an empty plan directory')
    original=file_inventory(vault)
    if '00-Catalog.json' in original:
        raise ValueError('Already restructured; maintain the existing hierarchy instead')
    work.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(work/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,data in original.items():z.writestr(name,data)
    output=dict(original)
    moves,anchors,documents,conservation={},{},{},[]
    group_rows={}
    for domain,groups in GROUPS.items():
        for group,(group_title,stems) in groups.items():
            base=f'{domain}/{group}'
            group_rows[base]=[]
            for stem in stems.split():
                old=f'{domain}/{stem}.md'
                if old not in original:continue
                meta,body=parse(original[old])
                if not meta.get('note_id'):raise ValueError(f'Missing note_id: {old}')
                title=str(meta.get('title') or title_for(body,stem))
                parts=split_body(body)
                split=(len(body)>LIMIT or (meta.get('note_type') in ['knowledge-index','method-group'] and len(body)>2200)) and len(parts)>1 and domain!='90-Templates'
                new=f'{base}/{stem}/00-Index.md' if split else f'{base}/{stem}.md'
                moves[old]=new
                documents[old]={'new':new,'meta':meta,'body':body,'title':title,'parts':parts if split else None}
                group_rows[base].append((new,title,str(meta.get('summary') or title)[:100]))
    # Large catalogues are indexes, not runtime expert/literature content.
    for old in ['50-Analysis-Methods/10-Experts/00-Index.md','50-Analysis-Methods/20-Literature/00-Index.md',
                '50-Analysis-Methods/99-Peer-Reviewed-References.md','50-Analysis-Methods/00-Index.md',
                '50-Analysis-Methods/00-Method-Selection-Guide.md']:
        meta,body=parse(original[old]);parts=split_body(body)
        if len(body)>2200:
            documents[old]={'new':old,'meta':meta,'body':body,'title':str(meta['title']),'parts':parts}
    # Date-scoped prose remains at its original entry path, with details below
    # it. The original observation status/date and all non-Markdown bytes stay.
    for old,data in original.items():
        if not old.endswith('.md') or old in documents:continue
        if old.startswith(('40-Design/ui-design-research/','40-Design/ui-design-assets/','50-Tests/ui-design-evidence/')):
            meta,body=parse(data);parts=split_body(body)
            if len(body)>LIMIT:
                documents[old]={'new':old,'meta':meta,'body':body,'title':str(meta.get('title') or title_for(body,Path(old).stem)),'parts':parts}
    for old,doc in documents.items():
        if doc['parts']:
            parent=Path(doc['new']).parent if doc['new'].endswith('/00-Index.md') and doc['new']!=old else Path(old).parent/(Path(old).stem+'-sections')
            doc['children']=[];doc['topic_indexes']=[]
            for i,(start,end,part) in enumerate(doc['parts'],1):
                # Keep each directory index short, even for long execution logs.
                bucket=(i-1)//8
                section_parent=parent/f'{bucket+1:02d}-topics' if len(doc['parts'])>12 else parent
                child=(section_parent/f'{i:02d}-section.md').as_posix()
                doc['children'].append((child,start,end,part))
                for _,_,heading in heading_spans(part):
                    anchors.setdefault((old,heading),child)
                    anchors.setdefault((old,slug(heading)),child)
                    anchors.setdefault((old,plain_heading(heading)),child)
                    anchors.setdefault((old,slug(plain_heading(heading))),child)
        else:
            for _,_,heading in heading_spans(doc['body']):
                anchors[(old,heading)]=doc['new'];anchors[(old,slug(heading))]=doc['new']
                anchors[(old,plain_heading(heading))]=doc['new'];anchors[(old,slug(plain_heading(heading)))]=doc['new']
    def rewrite(body,old,new):return rewrite_links(body,old,new,vault,original,moves,anchors)
    for old,doc in documents.items():
        meta=dict(doc['meta']);meta.setdefault('summary',doc['title'][:140]);meta.setdefault('tags',['gurumoji/program'])
        if doc['parts']:
            meta['note_type']='section-index';meta['content_updated']=DATE
            meta['source_sha256']=sha(original[old]);meta['source_path']=old
            rows=[]
            for i,(child,start,end,part) in enumerate(doc['children'],1):
                title=title_for(part,'前提・位置づけ')
                child_meta={k:v for k,v in doc['meta'].items() if k not in ['note_id','title','summary','aliases']}
                child_meta.update({'note_id':str(doc['meta']['note_id'])+f'-section-{i:02d}',
                    'note_type':'reference-section','title':doc['title']+'：'+title,
                    'summary':f'{title}。出典ノート「{doc["title"]}」の分割本文。',
                    'parent_note_id':doc['meta']['note_id'],'source_path':old,
                    'source_sha256':sha(original[old]),'source_body_lines':[doc['body'][:start].count('\n')+1,doc['body'][:end].count('\n')],
                    'split_on':DATE})
                child_meta.setdefault('tags',['gurumoji/program'])
                prefix=f'# {doc["title"]}：{title}\n\n親索引・状態・確認版：[[{doc["new"][:-3]}]]。必要な本文だけを取得する。\n\n'
                # Original text is copied without summarising or reinterpreting it.
                repeated_header=table_header(doc['body'],start,part)
                output[child]=pack(child_meta,prefix+rewrite(repeated_header+part,old,child))
                rows.append((child,plain_heading(title),f'本文 {len(part):,}字'))
            if len(rows)>12:
                grouped=[]
                parent=Path(doc['children'][0][0]).parent.parent
                for offset in range(0,len(rows),8):
                    batch=rows[offset:offset+8];number=offset//8+1
                    path=(parent/f'{number:02d}-topics/00-Index.md').as_posix()
                    title=f'{batch[0][1]} ～ {batch[-1][1]}' if len(batch)>1 else batch[0][1]
                    output[path]=small_index(str(doc['meta']['note_id'])+f'-topics-{number:02d}',title,batch)
                    grouped.append((path,title,f'{len(batch)}論点の入口'))
                rows=grouped
            body=f'# {doc["title"]}\n\n{meta["summary"]}\n\n'
            body+=f'状態は元資料の `{doc["meta"].get("status", "unknown")}` を引き継ぐ。改装日は内容の再検証日ではない。\n\n'
            body+='## 必要な論点だけ読む\n\n'+'\n'.join(f'- [[{p[:-3]}|{t}]] — {s}' for p,t,s in rows)
            output[doc['new']]=pack(meta,body)
            conservation.append({'source':old,'sha256':sha(original[old]),'body_chars':len(doc['body']),
                'reconstructed_sha256':sha(''.join(p for _,_,p in doc['parts']).encode('utf-8')),
                'original_body_sha256':sha(doc['body'].encode('utf-8')),'sections':[p for p,_,_,_ in doc['children']]})
        else:
            output[doc['new']]=pack(meta,rewrite(doc['body'],old,doc['new']))
        if doc['new']!=old:
            redirect={'note_id':str(doc['meta']['note_id'])+'-legacy-path','note_type':'path-redirect',
                'title':doc['title']+'（移動先案内）','summary':'本文と同じnote_idは移動先に保持。通常検索は移動先を使用する。',
                'status':'deprecated','updated':DATE,'redirect_to':doc['new'],'tags':['gurumoji/redirect']}
            body=f'# {doc["title"]}\n\n本文：[[{doc["new"][:-3]}|{doc["title"]}]]。旧パスの互換案内。\n'
            # Old external #heading links still have a landing point.
            for _,level,heading in heading_spans(doc['body']):
                if level==1:continue
                target=anchors.get((old,heading),doc['new'])
                body+='\n'+'#'*level+' '+heading+'\n\n'+f'[[{target[:-3]}#{plain_heading(heading)}|移動した本文を読む]]\n'
            output[old]=pack(redirect,body)
    # Rewrite all remaining prose notes, including date-scoped evidence. Assets
    # and machine-read expert/literature note bytes are deliberately not touched.
    protected=('50-Analysis-Methods/10-Experts/','50-Analysis-Methods/20-Literature/','50-Analysis-Methods/08-Common-Knowledge/')
    for old,data in original.items():
        if not old.endswith('.md') or old in documents:continue
        if old.startswith(protected):continue
        meta,body=parse(data)
        rewritten=rewrite(body,old,old)
        if rewritten!=body:output[old]=pack(meta,rewritten)
    # Add short domain/responsibility indexes, with facts on their own pages.
    for base,rows in group_rows.items():
        group=base.split('/')[1];domain=base.split('/')[0]
        output[base+'/00-Index.md']=small_index('index-'+base.lower().replace('/','-'),GROUPS[domain][group][0],rows)
    for domain,groups in GROUPS.items():
        rows=[(f'{domain}/{g}/00-Index.md',title,'この責務の資料と論点別入口') for g,(title,_) in groups.items()]
        if domain=='40-Design':
            rows.extend([(p,t,s) for p,t,s in [
                ('40-Design/ui-design-assets/2026-10-02/README.md','画面案・画像','2026-10-02の保存版'),
                ('40-Design/ui-design-research/2026-10-02/00-Index.md','UI研究・prompt調査','出典と確認範囲から選ぶ')]])
        if domain=='50-Tests':rows.append(('50-Tests/ui-design-evidence/2026-10-02/README.md','UI設計の証拠','日付と対象版を固定した記録'))
        output[domain+'/00-Index.md']=small_index('index-'+domain.lower(),DOMAIN_TITLES[domain],rows)
    research_rows=[]
    for name in sorted(original):
        if name.startswith('40-Design/ui-design-research/2026-10-02/') and name.endswith('.md'):
            meta,body=parse(original[name]);title=str(meta.get('title') or title_for(body,Path(name).stem))
            research_rows.append((name,title,str(meta.get('summary') or title)[:100]))
    output['40-Design/ui-design-research/2026-10-02/00-Index.md']=small_index('index-ui-research-20261002','UI研究とprompt調査（2026-10-02）',research_rows)
    rows=[(f'{d}/00-Index.md',t,'対象領域を選び、責務・論点の順に絞る') for d,t in DOMAIN_TITLES.items()]
    output['00-Index.md']=small_index('program-index','Software Vault 索引',rows,
        '領域 → 責務 → 論点の順に必要なノートだけ取得する入口。コード・設定が実装の正本。')
    output['00-Home.md']=small_index('program-home','Gurumoji プログラム資料',[
        ('00-AI-Entry.md','作業から選ぶ','AI・開発者の最初の取得先'),('00-Index.md','領域から選ぶ','全分野の索引'),
        (moves['40-Design/program-vault-rules.md'],'保存・取得ルール','改装方針と検証・復元の記録')],
        'Gurumojiの設計・仕様・検証を段階的に読むSoftware Vault。研究データは別Vault。')
    task_rows=[('10-Architecture/00-Index.md','構成・起動','対象の境界とコードへ'),
        ('20-Modules/00-Index.md','個別機能・不具合','責務と隣接テストへ'),
        ('30-Data/00-Index.md','保存形式・revision','対象の保存契約へ'),
        ('40-Design/40-Storage/00-Index.md','Vault・同期・移行','所有権と現行実装を照合'),
        ('40-Design/10-Analysis/00-Index.md','分析コア・LLM実行','現行と提案を区別'),
        ('40-Design/30-Interface/00-Index.md','UI設計・改善','設計契約と必要な受入へ'),
        ('50-Analysis-Methods/00-Index.md','手法・専門家・文献','選んだ手法と根拠だけ取得'),
        ('50-Tests/00-Index.md','検証','必要な層と未実行範囲を確認'),
        ('60-Operations/00-Index.md','運用・引継ぎ','対象の手順・日付だけ読む')]
    output['00-AI-Entry.md']=small_index('program-ai-entry','AI向けタスク別入口',task_rows,
        '最初はこの入口だけ。該当する責務の索引 → summary → 必要な本文の順で取得する。')
    entry_meta,entry_body=parse(output['00-AI-Entry.md'])
    entry_body+='\n\n「Obsidianを更新」は[既存のGit更新手順](../OBSIDIAN_VAULTS.md#プログラム資料vaultの更新)のcheck → 対象提示 → applyを使う。競合は上書きせず判断を待つ。\n'
    output['00-AI-Entry.md']=pack(entry_meta,entry_body)
    # Preserve the original governance text in its new place and record this
    # design decision once, rather than creating a second narrative report.
    rules=moves['40-Design/program-vault-rules.md']
    meta,body=parse(output[rules])
    body+='\n\n## 2026-10-11 段階取得のための改装\n\n'
    body+='- 領域 → 責務 → 論点・工程で分類し、入口は本文を複製しない。大きい本文は見出し単位で分割する。\n'
    body+='- 既存のnote_idは本文または本文索引へ保持する。旧パスはpath-redirectとし、通常検索から除外する。\n'
    body+='- 専門家の実行定義、知識7ノート、文献本文、共通知識の固定パスとbytesを維持する。過去の観測JSON・画像・manifestも変更しない。\n'
    body+='- source_sha256/source_path/source_body_linesは分割前の出所。改装日は内容の再検証を意味しない。読めない既存本文は推測修復せず保存する。\n'
    body+='- 00-Catalog.jsonは再生成可能な取得索引。scripts/build_program_vault_catalog.pyで更新し、本文の正本にはしない。\n'
    body+='- scripts/restructure_program_vault.py planは別フォルダーにbefore.zip・staged・plan.jsonを作る。apply/restoreはhashで後続編集を検出して停止する。\n'
    body+='- 取得は--scopeで領域、--note-idでIDを選び、--metadata-onlyまたは--sectionで必要量を限定する。全Vaultの本文をコンテキストへ渡さない。\n'
    output[rules]=pack(meta,body)
    staged=work/'staged';staged.mkdir()
    for name,data in output.items():
        p=staged/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    from build_program_vault_catalog import build_catalog
    catalogue=build_catalog(staged)
    output['00-Catalog.json']=(json.dumps(catalogue,ensure_ascii=False,indent=2,default=str)+'\n').encode('utf-8')
    (staged/'00-Catalog.json').write_bytes(output['00-Catalog.json'])
    writes={n:sha(d) for n,d in output.items() if original.get(n)!=d}
    before_notes=[len(parse(d)[1]) for n,d in original.items() if n.endswith('.md')]
    after_notes=[len(parse(d)[1]) for n,d in output.items() if n.endswith('.md') and parse(d)[0].get('note_type')!='path-redirect']
    plan={'schema_version':VERSION,'vault':str(vault),'work':str(work),'date':DATE,
        'before':{n:sha(d) for n,d in original.items()},'writes':writes,'moves':moves,
        'conservation':conservation,'metrics':{'before_notes':len(before_notes),'after_content_notes':len(after_notes),
        'legacy_redirects':len(moves),'split_documents':len(conservation),'max_body_before':max(before_notes),
        'max_body_after':max(after_notes),'root_index_body_before':len(parse(original['00-Index.md'])[1]),
        'root_index_body_after':len(parse(output['00-Index.md'])[1])}}
    (work/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(plan['metrics'],ensure_ascii=False,indent=2))
    print(f'Plan: {work / "plan.json"}; no source Vault files changed')
    return plan

def atomic(path: Path,data: bytes):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.'+path.name+'.',delete=False) as f:
        temporary=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
    try:os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def execute(plan_path: Path, restore=False):
    plan=json.loads(plan_path.read_text(encoding='utf-8'));root=Path(plan['vault']).resolve();work=plan_path.resolve().parent
    # Paths from a reviewable local plan must still be checked before mutations.
    for name in [*plan['before'],*plan['writes']]:
        p=(root/name).resolve()
        if Path(name).is_absolute() or not p.is_relative_to(root) or any(x.startswith('.') for x in Path(name).parts):
            raise ValueError('Unsafe path in plan: '+name)
    current=file_inventory(root)
    if restore:
        changes=[n for n,digest in plan['writes'].items() if n in current and sha(current[n])!=digest and sha(current[n])!=plan['before'].get(n)]
        if changes:raise ValueError('Preserve subsequent edits before restore: '+', '.join(changes))
        with zipfile.ZipFile(work/'before.zip') as z:
            restored={name:z.read(name) for name in plan['writes'] if name in plan['before']}
            for name,data in restored.items():
                if sha(data)!=plan['before'][name]:raise ValueError('Backup hash mismatch: '+name)
            for name in plan['writes']:
                p=root/name
                if name in plan['before']:
                    atomic(p,restored[name])
                elif p.exists():p.unlink()
        print('Restored changed files from before.zip; unrelated files/settings left intact')
    else:
        changed=[n for n,digest in plan['before'].items() if n not in current or sha(current[n])!=digest]
        added=set(current)-set(plan['before'])
        if changed or added:raise ValueError('Vault changed since plan; re-plan: '+', '.join(sorted(set(changed)|added)))
        for name,digest in plan['writes'].items():
            data=(work/'staged'/name).read_bytes()
            if sha(data)!=digest:raise ValueError('Staging hash mismatch: '+name)
        progress=[]
        for name in plan['writes']:
            p=root/name
            if name in plan['before'] and (not p.exists() or sha(p.read_bytes())!=plan['before'][name]):
                raise ValueError('Concurrent edit; restore or re-plan: '+name)
            if name not in plan['before'] and p.exists():raise ValueError('Concurrent file creation: '+name)
            atomic(p,(work/'staged'/name).read_bytes());progress.append(name)
            atomic(work/'applied.json',json.dumps(progress,ensure_ascii=False,indent=2).encode('utf-8'))
        print(f'Applied {len(progress)} Markdown/catalogue files; backup: {work / "before.zip"}')

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan');p.add_argument('--vault',type=Path,required=True);p.add_argument('--work',type=Path,required=True)
    for command in ['apply','restore']:
        p=sub.add_parser(command);p.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='plan':stage(args.vault,args.work)
    else:execute(args.plan,args.command=='restore')

if __name__=='__main__':main()

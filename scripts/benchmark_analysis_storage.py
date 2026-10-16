"""Cold synthetic saves with the same fixture and payload across source versions."""
import argparse
from contextlib import contextmanager
import inspect
import json
from pathlib import Path
import sqlite3
import statistics
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,default=ROOT)
    parser.add_argument('--package-version',type=int,default=1,choices=(1,2))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();sys.path.insert(0,str(args.source_root.resolve()/'src'))
    from gurumoji.analysis_store import AnalysisStore,initialize_store
    from gurumoji.analysis_core import fingerprint
    fixture=json.loads((ROOT/'tests/fixtures/analysis_three_conversations.json').read_text(encoding='utf-8'))
    timings=[];sizes=[]
    for repeat in range(3):
        with tempfile.TemporaryDirectory(prefix='gurumoji-storage-benchmark-') as temporary:
            root=Path(temporary);database=root/'library.sqlite3'
            @contextmanager
            def connect():
                db=sqlite3.connect(database);db.row_factory=sqlite3.Row
                try:
                    with db:yield db
                finally:db.close()
            with connect() as db:
                db.execute('CREATE TABLE application_metadata(key TEXT PRIMARY KEY,value TEXT)')
                db.execute('CREATE TABLE speaker_registry(id TEXT)')
                db.execute('CREATE TABLE library_items(id TEXT PRIMARY KEY)')
                initialize_store(db)
            store=AnalysisStore(database,connect)
            for index,conversation in enumerate(fixture['conversations']):
                analysis=conversation['analysis'];item_id=analysis['item']['id']
                with connect() as db:db.execute('INSERT INTO library_items VALUES (?)',(item_id,))
                rows=[{'segment_id':analysis['segments'][i%len(analysis['segments'])]['id'],'value':i,'label':'架空の集計値'} for i in range(1000)]
                result={'schema_version':1,'parameters':{'synthetic':True},'methods':[],'scores':rows}
                options={'package_version':args.package_version} if 'package_version' in inspect.signature(store.save).parameters else {}
                if args.package_version==2 and not options:raise ValueError('source does not support package v2')
                started=time.perf_counter()
                run=store.save(item_id=item_id,kind='text_analysis',snapshot=analysis,result=result,datasets={'scores':(list(rows[0]),rows)},
                    request_id=f'synthetic-{index}',input_fingerprint=fingerprint(analysis),source_revision=analysis['item']['revision_count'],
                    analysis_revision=analysis['item']['analysis_revision'],publish=False,**options)
                timings.append(time.perf_counter()-started)
                readable=store.readable_package(run['id']) if hasattr(store,'readable_package') else store.verified_package(run['id'])
                if any(readable[1].get(key)!=value for key,value in result.items() if key!='schema_version'):
                    raise ValueError('saved scientific values differ from fixture')
            sizes.append(sum(p.stat().st_size for p in root.rglob('*') if p.is_file()))
    report={'fixture_hash':fingerprint(fixture),'repetitions':3,'conversations_per_repetition':3,'rows_per_conversation':1000,
        'package_version':args.package_version,'cold_save_seconds':timings,'median_save_seconds':statistics.median(timings),
        'total_bytes':sizes,'median_total_bytes':statistics.median(sizes),'semantic_parity':True,'real_user_data_accessed':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('package_version','median_save_seconds','median_total_bytes','semantic_parity')},ensure_ascii=False))


if __name__=='__main__':main()

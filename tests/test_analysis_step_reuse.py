"""New-pipeline committed-step reuse with temporary SQLite and synthetic data."""
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import test_analysis_definition_safety as support
from test_analysis_core_decisions import validate_schema, ROOT
from gurumoji import analysis_core as core
from gurumoji.analysis_pipeline import initialize_pipeline_store, _transition_state


class StepReuseTests(unittest.TestCase):
    setUp=support.DefinitionSafetyTests.setUp
    connect=support.DefinitionSafetyTests.connect
    save_result=support.DefinitionSafetyTests.save_result
    payload=support.DefinitionSafetyTests.payload
    start=support.DefinitionSafetyTests.start
    save=support.DefinitionSafetyTests.save

    def run_new(self, request, **extra):
        pid=self.start(request_id='reuse-synthetic-request-'+request,definition_ids=[],mode='automatic',**extra)
        self.service._run(pid,'http://synthetic.invalid')
        return pid, self.service.status('synthetic',pid)

    def steps(self,pid):
        with self.connect() as connection:
            return {r['step_id']:dict(r) for r in connection.execute('SELECT * FROM analysis_step_attempts WHERE pipeline_id=?',(pid,))}

    def test_new_pipeline_reuses_committed_sibling_after_failure_and_cancellation(self):
        original=self.service.method_runner
        def fail(step,snapshot):
            if step=='conversation_dynamics':
                raise OSError('synthetic failure')
            return original(step,snapshot)
        with patch.object(self.service,'method_runner',side_effect=fail):
            old,state=self.run_new('original')
        self.assertEqual(state['status'],'waiting')
        self.service.cancel('synthetic',old)
        self.assertEqual(self.service.status('synthetic',old)['status'],'cancelled')
        before=self.steps(old)
        with patch.object(self.service,'method_runner',wraps=original) as runner:
            new,state=self.run_new('cancelled')
        self.assertEqual(state['status'],'completed')
        self.assertEqual([call.args[0] for call in runner.call_args_list],['conversation_dynamics'])
        after=self.steps(new)
        self.assertEqual(after['participation']['status'],'reused')
        self.assertEqual(after['participation']['reused_from'],before['participation']['attempt_id'])
        self.assertEqual(after['participation']['artifact_json'],before['participation']['artifact_json'])
        self.assertEqual(after['participation']['artifact_hash'],before['participation']['artifact_hash'])
        self.assertEqual(after['participation']['reused_at'],before['participation']['ended_at'])
        self.assertEqual(self.steps(old),before)
        self.assertEqual(self.saved[-1]['result']['parameters']['reused_steps'][0]['reused_from'],before['participation']['attempt_id'])
        self.assertEqual(after['chart_specs']['status'],'committed')
        with patch.object(self.service,'method_runner',wraps=original) as runner:
            _,none=self.run_new('none',reuse='none')
        self.assertEqual(none['status'],'completed')
        self.assertEqual(runner.call_count,2)
        self.assertEqual(self.saved[-1]['datasets'],self.saved[-2]['datasets'])
        self.assertEqual(self.saved[-1]['result']['methods'],self.saved[-2]['result']['methods'])

    def test_terminal_failed_source_is_reusable_without_reopening_it(self):
        original=self.service.method_runner
        def fail(step,snapshot):
            if step=='conversation_dynamics':
                raise OSError('synthetic failure')
            return original(step,snapshot)
        with patch.object(self.service,'method_runner',side_effect=fail):
            old,state=self.run_new('failed-source')
        self.assertEqual(state['status'],'waiting')
        with patch.object(self.service,'_run',side_effect=RuntimeError('synthetic unexpected')):
            self.service._run_guarded(old,'http://synthetic.invalid','synthetic-runtime',1)
        self.assertEqual(self.service.status('synthetic',old)['status'],'failed')
        with patch.object(self.service,'method_runner',wraps=original) as runner:
            _,state=self.run_new('after-failed')
        self.assertEqual(state['status'],'completed')
        self.assertEqual([call.args[0] for call in runner.call_args_list],['conversation_dynamics'])
        self.assertEqual(self.service.status('synthetic',old)['status'],'failed')

    def test_hash_mismatch_malformed_and_legacy_candidates_recompute(self):
        old,_=self.run_new('bad-source')
        for fault,value in [('artifact_json','{"altered":true}'),('artifact_json','bad-json'),('artifact_hash',''),('reuse_key','')]:
            with self.subTest(fault=fault,value=value):
                before=self.steps(old)['participation']
                with self.connect() as connection:
                    connection.execute(f'UPDATE analysis_step_attempts SET {fault}=? WHERE attempt_id=?',(value,before['attempt_id']))
                # Exclude newer rows from this candidate test.
                original=self.service.method_runner
                with patch.object(self.service,'method_runner',wraps=original) as runner:
                    pid,state=self.run_new('fault-'+fault+str(len(value)))
                self.assertEqual(state['status'],'completed')
                self.assertIn('participation',[call.args[0] for call in runner.call_args_list])
                with self.connect() as connection:
                    connection.execute("UPDATE analysis_step_attempts SET reuse_key='' WHERE pipeline_id=?",(pid,))
                    connection.execute(f'UPDATE analysis_step_attempts SET {fault}=? WHERE attempt_id=?',(before[fault],before['attempt_id']))

    def test_input_registry_algorithm_library_spec_and_definition_change_keys(self):
        spec={'step_id':'participation','parents':['freeze_input'],'milestone':'M2'}
        args=dict(library='library',item_id='synthetic',spec=spec,analysis_hash='hash',registry_version='v1',
                  algorithm_version='a1',definition_hashes=[])
        key=core.step_reuse_key(**args)
        for field,value in [('library','other'),('item_id','other'),('spec',{**spec,'required':True}),
                ('analysis_hash','other'),('registry_version','v2'),('algorithm_version','a2')]:
            with self.subTest(field=field):
                self.assertNotEqual(core.step_reuse_key(**{**args,field:value}),key)
        args['spec']={**spec,'step_id':'manual_measurement'}
        self.assertNotEqual(core.step_reuse_key(**args),core.step_reuse_key(**{**args,'definition_hashes':['new']}))
        self.run_new('input-original')
        self.snapshot['analysis']['segments'][0]['text']='changed input'
        with patch.object(self.service,'method_runner',wraps=self.service.method_runner) as runner:
            _,state=self.run_new('input-changed')
        self.assertEqual(state['status'],'completed'); self.assertEqual(runner.call_count,2)
        with patch('gurumoji.analysis_pipeline.REGISTRY_VERSION','new-registry'), patch.object(
                self.service,'method_runner',wraps=self.service.method_runner) as runner:
            self.run_new('registry-changed')
        self.assertEqual(runner.call_count,2)

    def test_bound_manual_definition_hash_reuse_and_change(self):
        self.save()
        old=self.start(request_id='manual-reuse-original')
        self.service._run(old,'http://synthetic.invalid')
        with patch('gurumoji.analysis_pipeline.measure_segments',side_effect=AssertionError('should reuse')):
            new=self.start(request_id='manual-reuse-copy')
            self.service._run(new,'http://synthetic.invalid')
        self.assertEqual(self.steps(new)['manual_measurement']['status'],'reused')
        self.save(expected_revision=1,source_columns=['duration'],measurement_rule='duration')
        newer=self.start(request_id='manual-reuse-changed')
        self.service._run(newer,'http://synthetic.invalid')
        self.assertEqual(self.steps(newer)['manual_measurement']['status'],'committed')
        self.assertEqual(self.saved[-1]['datasets']['measurements'][1][0]['measured_size'],60)

    def test_additive_schema_keeps_old_columns_and_rows_ineligible(self):
        connection=sqlite3.connect(':memory:');connection.row_factory=sqlite3.Row
        self.addCleanup(connection.close)
        connection.execute('''CREATE TABLE analysis_step_attempts (
            attempt_id TEXT PRIMARY KEY,pipeline_id TEXT,step_id TEXT,milestone TEXT,generation INTEGER,
            attempt INTEGER,status TEXT,directive_json TEXT,report_json TEXT,artifact_json TEXT,
            error_code TEXT,error TEXT,started_at TEXT,updated_at TEXT,ended_at TEXT)''')
        connection.execute("INSERT INTO analysis_step_attempts(attempt_id,status,artifact_json) VALUES ('legacy','committed','{}')")
        before=[tuple(r) for r in connection.execute('PRAGMA table_info(analysis_step_attempts)')]
        initialize_pipeline_store(connection)
        after=[tuple(r) for r in connection.execute('PRAGMA table_info(analysis_step_attempts)')]
        self.assertEqual(before,after[:-4])
        row=dict(connection.execute('SELECT * FROM analysis_step_attempts').fetchone())
        self.assertEqual([row[k] for k in ['reuse_key','artifact_hash','reused_from','reused_at']],['']*4)
        initialize_pipeline_store(connection)
        self.assertEqual(after,[tuple(r) for r in connection.execute('PRAGMA table_info(analysis_step_attempts)')])

    def test_decisions_validate_against_schema_and_reuse_needs_no_more_write_transactions(self):
        self.run_new('trace-original')
        original=self.service.connect
        counts=[]
        for reuse in ['none','auto']:
            transactions=[]
            @contextmanager
            def traced():
                with original() as connection:
                    statements=[];transactions.append(statements)
                    connection.set_trace_callback(statements.append)
                    yield connection
            with patch.object(self.service,'connect',traced):
                pid,state=self.run_new('trace-'+reuse,reuse=reuse)
            counts.append(sum(any(s.lstrip().upper().startswith(('UPDATE','INSERT','DELETE')) for s in tx) for tx in transactions))
            self.assertEqual(state['status'],'completed')
            if reuse=='auto':
                self.assertEqual(sum(s.startswith('SELECT attempt_id,step_id,status,reuse_key') for tx in transactions for s in tx),1)
            with original() as connection:
                decisions=[json.loads(r[0]) for r in connection.execute("SELECT payload_json FROM analysis_pipeline_events WHERE pipeline_id=? AND event_type='core_decision'",(pid,))]
            schema=json.loads((ROOT/'docs/program-vault/40-Design/analysis-design/core-control.schema.json').read_text(encoding='utf-8'))
            self.assertTrue(decisions)
            for event in decisions:
                validate_schema(event['value'],schema['$defs']['CoreDecision'],schema['$defs'])
                self.assertEqual(event['value']['pipeline_id'],'pipeline.'+pid)
                self.assertEqual(event['value']['fact_refs'][0]['sha256'],core.fingerprint(event['facts'])[7:])
            self.assertEqual([e['payload']['milestone'] for e in state['events'] if e['type']=='milestone_committed'],
                             [f'M{i}' for i in range(8)])
        print('synthetic_write_transactions none/auto:',counts)
        self.assertLessEqual(counts[1],counts[0])

    def test_reuse_none_and_invalid_policy_request_id_conflict(self):
        pid,_=self.run_new('policy')
        with self.assertRaises(core.AnalysisContractError) as error:
            self.start(request_id='reuse-synthetic-request-policy',definition_ids=[],mode='automatic',reuse='none')
        self.assertEqual(error.exception.code,'request_conflict')
        for value in ['invalid',[],None,True]:
            with self.subTest(value=value),self.assertRaises(core.AnalysisContractError):
                self.start(request_id='invalid-policy-request',definition_ids=[],reuse=value)

    def test_legacy_request_id_remains_idempotent_without_rewriting_frozen_plan(self):
        pid=self.start(request_id='legacy-reuse-request',definition_ids=[],mode='automatic')
        with self.connect() as connection:
            row=dict(connection.execute('SELECT * FROM analysis_pipeline_requests WHERE pipeline_id=?',(pid,)).fetchone())
            plan=json.loads(row['plan_json']);plan.pop('reuse');plan.pop('plan_hash')
            plan['plan_hash']=core.fingerprint(plan)
            binding=json.loads(row['binding_json']);binding['plan_hash']=plan['plan_hash']
            connection.execute('UPDATE analysis_pipeline_requests SET plan_json=?,plan_hash=?,binding_json=? WHERE pipeline_id=?',
                (json.dumps(plan),plan['plan_hash'],json.dumps(binding),pid))
            before=list(connection.iterdump())
        response,code=self.service.start('synthetic',self.payload(request_id='legacy-reuse-request',definition_ids=[],
            mode='automatic'),app_url='http://synthetic.invalid')
        self.assertEqual((response['pipeline_id'],code),(pid,200))
        with self.connect() as connection:
            self.assertEqual(before,list(connection.iterdump()))
        with self.assertRaises(core.AnalysisContractError):
            self.service.start('synthetic',self.payload(request_id='legacy-reuse-request',definition_ids=[],
                mode='automatic',reuse='none'),app_url='http://synthetic.invalid')

    def test_old_generation_cannot_adopt_reused_artifact(self):
        self.run_new('generation-original')
        pid=self.start(request_id='generation-reuse-new',definition_ids=[],mode='automatic')
        original=core.decide_reuse
        def change_generation(*args,**kwargs):
            result=original(*args,**kwargs)
            with self.connect() as connection:
                connection.execute('UPDATE analysis_pipeline_requests SET generation=2 WHERE pipeline_id=?',(pid,))
            return result
        with patch.object(core,'decide_reuse',side_effect=change_generation),self.assertRaises(core.AnalysisContractError):
            self.service._run(pid,'http://synthetic.invalid')
        self.assertNotIn('reused',[s['status'] for s in self.steps(pid).values()])


if __name__=='__main__':
    unittest.main()

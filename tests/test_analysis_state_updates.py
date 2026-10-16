"""Stage 2-1: exhaustive contracts, recovery/CAS and temporary SQLite only."""
from contextlib import contextmanager
import json
import re
from pathlib import Path
import sqlite3
import threading
import unittest
from unittest.mock import patch

import test_analysis_definition_safety as support
from gurumoji.analysis_core import (
    ALLOWED_TRANSITIONS, RESERVED_STATES, AnalysisContractError,
    EFFECTIVE_PUBLICATION_WRITERS, PUBLICATION_TARGETS,
    fingerprint, state_machine_contracts, transition_guard, validate_transition,
)
from gurumoji.analysis_pipeline import _transition_state, initialize_pipeline_store

ROOT = Path(__file__).resolve().parents[1]


class StateAuthorityTests(unittest.TestCase):
    def test_contract_matches_every_state_edge_guard_and_reserved_state(self):
        contract = json.loads((ROOT/'docs/program-vault/40-Design/analysis-design/core-control-contract.json').read_text(encoding='utf-8'))
        for machine, table in state_machine_contracts().items():
            self.assertEqual(contract['state_machines'][machine]['states'], table['states'])
            self.assertEqual(contract['state_machines'][machine]['transitions'], table['transitions'])
            self.assertEqual(contract['state_machines'][machine]['reserved'], table['reserved'])
            self.assertEqual(contract['state_machines'][machine]['rule_version'], table['rule_version'])
            for transition in table['transitions']:
                self.assertIn(transition['guard'], contract['guard_notes'])
        for machine, reserved in RESERVED_STATES.items():
            for state in reserved:
                self.assertEqual(ALLOWED_TRANSITIONS[machine][state], set())
                self.assertFalse(any(state in targets for targets in ALLOWED_TRANSITIONS[machine].values()))

    def test_all_unlisted_edges_and_wrong_guards_are_rejected(self):
        for machine, states in ALLOWED_TRANSITIONS.items():
            for current, targets in states.items():
                for target in states:
                    with self.subTest(machine=machine, current=current, target=target):
                        if target in targets:
                            validate_transition(machine, current, target, transition_guard(machine, current, target))
                            with self.assertRaises(AnalysisContractError) as error:
                                validate_transition(machine, current, target, 'arbitrary.valid_id')
                            self.assertEqual(error.exception.code, 'invalid_guard')
                        else:
                            with self.assertRaises(AnalysisContractError):
                                validate_transition(machine, current, target, 'unlisted.transition')


class StateUpdateTests(unittest.TestCase):
    setUp = support.DefinitionSafetyTests.setUp
    connect = support.DefinitionSafetyTests.connect
    save_result = support.DefinitionSafetyTests.save_result
    payload = support.DefinitionSafetyTests.payload
    start = support.DefinitionSafetyTests.start

    def accepted(self, **extra):
        return self.start(definition_ids=[], mode='automatic', **extra)

    def restart(self, pipeline_id):
        with self.connect() as connection:
            initialize_pipeline_store(connection)
        return self.service.status('synthetic', pipeline_id)

    def dump(self):
        with self.connect() as connection:
            return list(connection.iterdump())

    def test_repeated_get_never_writes_schedules_runs_or_advances_generation(self):
        pid = self.accepted()
        self.restart(pid)
        before = self.dump()
        with patch.object(self.service, '_schedule') as schedule, patch.object(self.service, 'retry') as retry, patch.object(self.service, 'method_runner') as run:
            for ensure_running in (True, False, True):
                response = self.service.status('synthetic', pid, ensure_running=ensure_running)
                self.assertEqual(response['status'], 'waiting')
                self.assertEqual(response['allowed_actions'], ['resume'])
                self.assertEqual(response['recovery'], {'pending': True, 'mode': 'manual', 'reason_code': ''})
            schedule.assert_not_called(); retry.assert_not_called(); run.assert_not_called()
        self.assertEqual(before, self.dump())

    def test_resume_uses_supplied_app_url_and_advances_once(self):
        pid = self.accepted()
        self.restart(pid)
        with patch.object(self.service, '_schedule') as schedule:
            result = self.service.resume('synthetic', pid, {}, app_url='https://configured.invalid/prefix/')
            schedule.assert_called_once_with(pid, 'https://configured.invalid/prefix/')
        self.assertEqual((result['status'], result['generation']), ('accepted', 2))
        with self.assertRaises(AnalysisContractError):
            self.service.resume('synthetic', pid, {}, app_url='https://configured.invalid/')

    def test_resume_rejects_input_revision_hash_policy_and_binding_changes_atomically(self):
        for fault, code in [('revision', 'revision_conflict'), ('input_hash', 'revision_conflict'),
                            ('snapshot', 'binding_conflict'), ('policy', 'provider_unavailable'),
                            ('binding', 'binding_conflict')]:
            with self.subTest(fault=fault):
                case = StateUpdateTests(); case.setUp()
                try:
                    pid = case.accepted(); case.restart(pid)
                    if fault == 'revision':
                        case.item['revision_count'] += 1
                    elif fault == 'input_hash':
                        case.snapshot['input_hash'] = 'sha256:changed'
                    else:
                        with case.connect() as connection:
                            row = dict(connection.execute('SELECT * FROM analysis_pipeline_requests').fetchone())
                            if fault == 'policy':
                                plan = json.loads(row['plan_json']); plan['provider_policy'] = 'unavailable'
                                plan['plan_hash'] = fingerprint({k: v for k, v in plan.items() if k != 'plan_hash'})
                                binding = json.loads(row['binding_json']); binding['plan_hash'] = plan['plan_hash']
                                connection.execute('UPDATE analysis_pipeline_requests SET plan_json=?,plan_hash=?,binding_json=?',
                                                   (json.dumps(plan), plan['plan_hash'], json.dumps(binding)))
                            else:
                                connection.execute('UPDATE analysis_pipeline_requests SET '+('snapshot_json' if fault == 'snapshot' else 'binding_json')+'=?', ('{}',))
                    before = case.dump()
                    with self.assertRaises(AnalysisContractError) as error:
                        case.service.resume('synthetic', pid, {}, app_url='http://synthetic.invalid')
                    self.assertEqual(error.exception.code, code)
                    self.assertEqual(case.dump(), before)
                finally:
                    case.doCleanups()

    def test_terminal_retry_and_resume_cannot_create_attempts_or_events(self):
        for state in ('cancelled', 'failed'):
            with self.subTest(state=state):
                pid = self.accepted(request_id='terminal-synthetic-request-'+state)
                with self.connect() as connection:
                    connection.execute('UPDATE analysis_pipeline_requests SET status=? WHERE pipeline_id=?', (state, pid))
                before = self.dump()
                for operation in (self.service.retry, self.service.resume):
                    with self.assertRaises(AnalysisContractError) as error:
                        operation('synthetic', pid, {}, app_url='http://synthetic.invalid')
                    self.assertEqual(error.exception.code, 'pipeline_terminal')
                self.assertEqual(before, self.dump())

    def test_restart_requires_resume_and_enforces_remaining_attempt_budget(self):
        pid = self.accepted()
        with self.connect() as connection:
            connection.execute("UPDATE analysis_step_attempts SET status='running',attempt=3 WHERE step_id='participation'")
        state = self.restart(pid)
        self.assertEqual(state['recovery']['reason_code'], 'retry_limit_reached')
        before = self.dump()
        with self.assertRaises(AnalysisContractError) as error:
            self.service.resume('synthetic', pid, {}, app_url='http://synthetic.invalid')
        self.assertEqual(error.exception.code, 'retry_limit_reached')
        with self.assertRaises(AnalysisContractError) as error:
            self.service.retry('synthetic', pid, {}, app_url='http://synthetic.invalid')
        self.assertEqual(error.exception.code, 'resume_required')
        self.assertEqual(before, self.dump())

    def test_simultaneous_resume_accepts_only_one_generation(self):
        pid = self.accepted(); self.restart(pid)
        barrier = threading.Barrier(2); results = []
        def resume():
            barrier.wait()
            try:
                results.append(self.service.resume('synthetic', pid, {}, app_url='http://synthetic.invalid')['generation'])
            except AnalysisContractError as error:
                results.append(error.code)
        workers = [threading.Thread(target=resume) for _ in range(2)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(5); self.assertFalse(worker.is_alive())
        self.assertCountEqual(results, [2, 'retry_in_progress'])

    def test_cas_rejects_old_pipeline_step_and_publication_generations(self):
        pid = self.accepted()
        with self.connect() as connection:
            attempt = connection.execute("SELECT attempt_id FROM analysis_step_attempts WHERE step_id='participation'").fetchone()[0]
            connection.execute('UPDATE analysis_pipeline_requests SET generation=2')
        before = self.dump()
        for machine, key, target in [('pipeline', (pid,), 'running'), ('step', (attempt,), 'checking'),
                                     ('publication', (pid, 'research'), 'publishing')]:
            # A selected synthetic publication is needed for pending→publishing.
            if machine == 'publication':
                with self.connect() as connection:
                    connection.execute("UPDATE analysis_pipeline_publications SET status='pending'")
                before = self.dump()
            with self.subTest(machine=machine), self.assertRaises(AnalysisContractError):
                with self.connect() as connection:
                    _transition_state(connection, machine, key, target, generation=1)
            self.assertEqual(self.dump(), before)

    def test_all_status_updates_use_cas_and_events_without_more_write_transactions(self):
        pid = self.accepted()
        self.trace_and_validate(pid, 63)

    def test_selected_publications_are_guarded_without_more_write_transactions(self):
        self.service.publish_result = lambda *args, **kwargs: {}
        self.service.publication_outcomes = lambda _: {role: {'status': 'published'} for role in EFFECTIVE_PUBLICATION_WRITERS}
        pid = self.accepted(publication_targets=list(PUBLICATION_TARGETS))
        self.trace_and_validate(pid, 69)
        self.assertEqual({row['status'] for row in self.service.status('synthetic', pid)['publications']}, {'published'})

    def trace_and_validate(self, pid, maximum):
        transactions = []
        original = self.service.connect
        @contextmanager
        def traced():
            with original() as connection:
                statements = []; transactions.append(statements)
                connection.set_trace_callback(statements.append)
                yield connection
        self.service.connect = traced
        self.service._run(pid, 'http://synthetic.invalid')
        writes = [tx for tx in transactions if any(s.lstrip().upper().startswith(('UPDATE', 'INSERT', 'DELETE')) for s in tx)]
        self.assertLessEqual(len(writes), maximum)  # 2026-10-12 pre-change synthetic trace
        for statements in writes:
            for sql in statements:
                if sql.startswith('UPDATE analysis_') and re.search(r'\bstatus\s*=', sql.split(' WHERE ')[0]):
                    self.assertIn('AND status=', sql); self.assertIn('AND generation=', sql)
        with self.connect() as connection:
            transitions = [json.loads(row[0]) for row in connection.execute("SELECT payload_json FROM analysis_pipeline_events WHERE event_type='state_transition'")]
        self.assertTrue(transitions)
        for event in transitions:
            validate_transition(event['machine'], event['from'], event['to'], event['guard_id'])
        self.assertEqual(self.service._pipeline_row(pid)['status'], 'completed')

    def test_legacy_publication_schema_adds_generation_without_changing_existing_columns(self):
        connection = sqlite3.connect(':memory:'); connection.row_factory = sqlite3.Row
        self.addCleanup(connection.close)
        connection.execute('''CREATE TABLE analysis_pipeline_publications (
            pipeline_id TEXT NOT NULL,target_role TEXT NOT NULL,result_run_id TEXT NOT NULL DEFAULT '',
            package_hash TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,attempt_id TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL,PRIMARY KEY(pipeline_id,target_role))''')
        before = list(connection.execute('PRAGMA table_info(analysis_pipeline_publications)'))
        initialize_pipeline_store(connection)
        after = list(connection.execute('PRAGMA table_info(analysis_pipeline_publications)'))
        self.assertEqual([tuple(r) for r in before], [tuple(r) for r in after[:-1]])
        self.assertEqual(after[-1]['name'], 'generation')


if __name__ == '__main__':
    unittest.main()

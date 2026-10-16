"""Table-driven pure decisions and the authoritative Schema (no runtime data)."""
import ast
import copy
import json
from pathlib import Path
import re
import unittest

from gurumoji import analysis_core as core

ROOT = Path(__file__).resolve().parents[1]


def validate_schema(value, schema, definitions):
    """Validate the small JSON Schema subset used by CoreDecision, without extras."""
    if '$ref' in schema:
        return validate_schema(value, definitions[schema['$ref'].split('/')[-1]], definitions)
    if 'anyOf' in schema:
        for alternative in schema['anyOf']:
            try:
                validate_schema(value, alternative, definitions)
                return
            except AssertionError:
                pass
        raise AssertionError(f'no matching Schema alternative: {value!r}')
    if 'enum' in schema:
        assert value in schema['enum'], value
    if schema.get('type') == 'null':
        assert value is None
    if schema.get('type') == 'string':
        assert isinstance(value, str)
        assert len(value) >= schema.get('minLength', 0)
        assert not schema.get('pattern') or re.search(schema['pattern'], value), value
    if schema.get('type') == 'object':
        assert isinstance(value, dict)
        assert set(schema.get('required', [])) <= value.keys()
        if schema.get('additionalProperties') is False:
            assert value.keys() <= schema['properties'].keys()
        for key, item in value.items():
            validate_schema(item, schema['properties'][key], definitions)
    if schema.get('type') == 'array':
        assert isinstance(value, list) and len(value) >= schema.get('minItems', 0)
        for item in value:
            validate_schema(item, schema['items'], definitions)


class CoreDecisionTests(unittest.TestCase):
    def setUp(self):
        self.context = {'pipeline_id': '0123456789', 'plan_hash': core.fingerprint({'plan': 1}),
                        'status': 'running', 'generation': 1, 'cancel_requested': 0, 'wait_reason': 'retry'}
        self.schema = json.loads((ROOT/'docs/program-vault/40-Design/analysis-design/core-control.schema.json').read_text(encoding='utf-8'))

    def check(self, result, action, reason=None):
        self.assertEqual(result['decision']['action'], action)
        self.assertEqual(result['decision']['reason_code'], reason)
        validate_schema(result['decision'], self.schema['$defs']['CoreDecision'], self.schema['$defs'])
        for effect in result['transitions']:
            core.validate_transition(effect['machine'], effect['from'], effect['to'], effect['guard_id'])

    def step(self, name='child', status='planned', **extra):
        return {'step_id': name, 'status': status, 'milestone': 'M2', 'attempt': 1, **extra}

    def test_parent_selection_and_gate_release_table(self):
        specs = {'parent': {'parents': []}, 'child': {'parents': ['parent']}}
        for parent, child, action, selected in [('planned','planned','dispatch',['parent']),
                ('committed','planned','dispatch',['child']), ('reused','planned','dispatch',['child']),
                ('not_applicable','planned','dispatch',['child']), ('failed','planned','fail',[]),
                ('committed','committed','release_gate',[])]:
            with self.subTest(parent=parent, child=child):
                result = core.decide_dispatch([self.step('parent',parent), self.step(status=child)], specs, 'M2', self.context)
                self.check(result, action, 'PARENT_INCOMPLETE' if action=='fail' else None)
                self.assertEqual(result['decision']['affected_steps'], selected)

    def test_applicability_table(self):
        for step, allow, definitions, targets, excluded in [('outline_scope',True,True,True,True),
                ('comparison_scope',True,True,True,True), ('manual_measurement',True,False,True,True),
                ('manual_measurement',True,True,True,False), ('publish_result',True,True,False,True),
                ('publish_result',True,True,True,False), ('outline_scope',False,False,False,False)]:
            with self.subTest(step=step, allow=allow, definitions=definitions, targets=targets):
                self.check(core.decide_applicability(step, {'allow_not_applicable':allow}, has_definitions=definitions,
                    has_targets=targets, context=self.context), 'mark_not_applicable' if excluded else 'dispatch',
                    'NOT_SELECTED' if excluded else None)

    def test_failure_and_unexpected_exception_table_preserves_unknown_fallback(self):
        for code, reason in [('publication_failed','PUBLICATION_FAILED'), ('execution_failed','UNKNOWN_EXECUTION_FAILURE'),
                ('unmapped-code','UNKNOWN_EXECUTION_FAILURE'), ('no_valid_input','EMPTY_EFFECTIVE_DATASET')]:
            for cancelled, unexpected in [(False,False),(False,True),(True,False),(True,True)]:
                with self.subTest(code=code, cancelled=cancelled, unexpected=unexpected):
                    result = core.decide_failure([{'step_id':'child','code':code}], cancelled=cancelled,
                        unexpected=unexpected,context=self.context)
                    self.check(result,'cancel' if cancelled else 'fail' if unexpected else 'retry',
                        'USER_CANCELLED' if cancelled else reason)
                    self.assertEqual(result['wait_reason'],'publication' if not cancelled and code=='publication_failed' else 'retry')

    def test_completion_table(self):
        for status, action in [('published','commit'),('not_selected','commit'),('pending','reconcile'),
                ('failed','reconcile'),('unknown','reconcile'),('conflict','reconcile')]:
            with self.subTest(status=status):
                self.check(core.decide_completion([{'status':status}],self.context),action,
                           None if action=='commit' else 'PUBLICATION_FAILED')

    def test_restart_and_cancel_settlement_table(self):
        for status, requested, action in [('accepted',0,'reconcile'),('running',0,'reconcile'),
                ('accepted',1,'cancel'),('running',1,'cancel'),('cancelling',0,'cancel')]:
            context = {**self.context,'status':status,'cancel_requested':requested}
            with self.subTest(status=status, requested=requested):
                self.check(core.decide_restart(context),action,'USER_CANCELLED' if action=='cancel' else 'PROCESS_RESTART')
        for state in ['planned', *core.ACTIVE_STEP_STATES, 'committed','reused','failed','cancelled','interrupted']:
            with self.subTest(step=state):
                step = self.step(status=state)
                self.check(core.decide_cancel_step(step,self.context),'cancel','USER_CANCELLED')
                result = core.decide_restart_step(step,cancelled=False,context=self.context)
                self.check(result,'reconcile','PROCESS_RESTART')
                self.assertEqual(bool(result['transitions']),state in core.ACTIVE_STEP_STATES)
        for state in ['accepted','running','waiting','cancelling']:
            self.check(core.decide_cancel_pipeline({**self.context,'status':state}),'cancel','USER_CANCELLED')
        for state in ['checking','ready','running','validating','persisting']:
            for cancelled in [False,True]:
                self.check(core.decide_failed_attempt(self.step(status=state),error_code='unmapped',cancelled=cancelled,
                    context=self.context),'cancel' if cancelled else 'fail','USER_CANCELLED' if cancelled else 'UNKNOWN_EXECUTION_FAILURE')

    def test_retry_candidates_attempt_limit_and_restart_table(self):
        context = {**self.context,'status':'waiting'}
        for state, attempt, restart, error in [('failed',1,False,''),('interrupted',2,True,''),
                ('failed',3,False,'retry_limit_reached'), ('interrupted',3,True,'retry_limit_reached'),
                ('planned',1,True,''),('committed',1,True,''),('committed',1,False,'nothing_to_retry'),
                ('running',1,False,'retry_in_progress')]:
            with self.subTest(state=state,attempt=attempt,restart=restart):
                result=core.decide_retry([self.step(status=state,attempt=attempt)],context,target=None,restart_pending=restart)
                self.check(result,'fail' if error else 'retry','RETRY_EXHAUSTED' if error=='retry_limit_reached'
                           else 'RETRY_UNAVAILABLE' if error else None)
                self.assertEqual(result['error_code'],error)
        steps=[self.step('a','failed'),self.step('b','failed')]
        self.assertEqual(core.decide_retry(steps,context,target='b',restart_pending=False)['decision']['affected_steps'],['b'])
        self.assertEqual(core.decide_retry([self.step('publish_result','committed')],{**context,'wait_reason':'publication'},
            target=None,restart_pending=False)['decision']['affected_steps'],['publish_result'])

    def test_display_derivation_table(self):
        for states, status in [([], 'pending'),(['planned'],'pending'),(['reused','not_applicable'],'committed'),
                (['running','failed'],'failed'),(['cancelled','running'],'active'),(['cancelled'],'cancelled')]:
            with self.subTest(states=states):
                self.assertEqual(core.derive_milestone_status([self.step(status=s) for s in states]),status)
        for status, wait, steps, restart, actions in [('completed','',[],False,['view_results']),
                ('failed','',[],False,[]),('cancelled','',[],False,[]),('running','',[],False,['cancel']),
                ('waiting','retry',[self.step(status='failed')],False,['cancel','retry_failed']),
                ('waiting','publication',[],False,['cancel','retry_publication']),
                ('waiting','retry',[],True,['resume']),
                ('waiting','retry',[self.step(status='interrupted',attempt=3)],True,['cancel'])]:
            with self.subTest(status=status, wait=wait,restart=restart):
                self.assertEqual(core.derive_allowed_actions({**self.context,'status':status,'wait_reason':wait},steps,
                    restart_pending=restart),actions)

    def test_reuse_verification_and_purity(self):
        candidate={'status':'committed','artifact_json':'{"result":1}','artifact_hash':core.fingerprint({'result':1}),
                   'reuse_key':'key','attempt_id':'source','ended_at':'2026-10-12'}
        for patch, mode, action in [({},'auto','reuse'),({},'none','dispatch'),({'status':'reused'},'auto','dispatch'),
                ({'reuse_key':'different'},'auto','dispatch'),({'artifact_hash':''},'auto','dispatch'),
                ({'artifact_json':'bad'},'auto','dispatch'),({'artifact_json':'{"result":2}'},'auto','dispatch')]:
            candidates=[{**candidate,**patch}]; before=copy.deepcopy(candidates)
            with self.subTest(patch=patch,mode=mode):
                result=core.decide_reuse('participation','key',candidates,mode=mode,context=self.context)
                self.check(result,action,'REUSED_COMMITTED_STEP' if action=='reuse' else None)
                self.assertEqual(candidates,before)
                self.assertEqual(result,core.decide_reuse('participation','key',candidates,mode=mode,context=self.context))
        tree=ast.parse((ROOT/'src/gurumoji/analysis_core.py').read_text(encoding='utf-8-sig'))
        forbidden={'sqlite3','flask','os','socket','urllib','requests','http','pathlib','subprocess'}
        for node in ast.walk(tree):
            imports=([a.name for a in node.names] if isinstance(node,ast.Import)
                     else [node.module or ''] if isinstance(node,ast.ImportFrom) else [])
            self.assertFalse({name.split('.')[0] for name in imports} & forbidden)

    def test_only_capture_clock_is_excluded_from_reuse_identity(self):
        analysis={'generated_at':'time1','segments':[{'text':'synthetic'}],
                  'transformer':{'generated_at':'model-time','model':'model1'}}
        self.assertEqual(core.reuse_analysis_hash(analysis),core.reuse_analysis_hash({**analysis,'generated_at':'time2'}))
        self.assertNotEqual(core.fingerprint(analysis),core.fingerprint({**analysis,'generated_at':'time2'}))
        self.assertNotEqual(core.reuse_analysis_hash(analysis),core.reuse_analysis_hash({**analysis,
                            'transformer':{'generated_at':'new-result','model':'model1'}}))


if __name__=='__main__':
    unittest.main()

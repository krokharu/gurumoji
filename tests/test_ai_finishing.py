import copy
import json
import unittest

import ai_finishing as finishing


class AiFinishingTests(unittest.TestCase):
    def setUp(self):
        self.segments = [{'id': 'a', 'speaker': 'A', 'start': 2, 'end': 6, 'text': '賛成ではない。'},
                         {'id': 'b', 'speaker': 'B', 'start': 7, 'end': 10, 'text': '検討します。'}]
        self.outline = {'sections': [{'title': '検討', 'bullets': ['賛成ではない。検討する。']}]}

    def clean(self, call, segments=None, cancel=lambda: None):
        return finishing.clean_transcript(segments or self.segments, call, lambda *_: None, cancel,
                                         outline=self.outline)

    def echo(self, system, prompt, name, schema):
        return {'items': [{'id': r['id'], 'text': r['text'], 'noise_candidate': False, 'reason': ''}
                          for r in json.loads(prompt.split('\n', 1)[1])['targets']]}

    def test_recommended_cleanup_calls_llm_only_for_jev_candidates(self):
        reviews = {
            "a": {"flagged": True, "decision": "cutoff_suspected"},
            "b": {"flagged": False, "decision": "complete_or_natural"},
        }
        calls = []

        def call(system, prompt, name, schema):
            calls.append((system, json.loads(prompt.split('\n', 1)[1]), name, schema))
            return {
                "confirmed_problem": True,
                "needs_more_context": False,
                "issue_type": "cutoff",
                "text": "賛成ではありません。",
                "reason": "語尾の断裂を前後文脈から補正",
            }

        result = finishing.repair_recommended_segments(
            self.segments, reviews, call, lambda *_: None, lambda: None,
            effort="medium",
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2], "transcript_recommended_cleanup")
        self.assertEqual(calls[0][1]["target_segment_id"], "a")
        self.assertEqual(len(calls[0][1]["conversation_window"]), 1)
        self.assertEqual(result[0]["text"], "賛成ではありません。")
        self.assertTrue(result[0]["recommended_review"]["llm"]["replacement_applied"])
        self.assertNotIn("recommended_review", result[1])

    def test_unconfirmed_recommended_candidate_keeps_original_text(self):
        result = finishing.repair_recommended_segments(
            self.segments,
            {"a": {"flagged": True}},
            lambda *_args: {
                "confirmed_problem": False,
                "needs_more_context": False,
                "issue_type": "none",
                "text": "モデルが勝手に変えた文",
                "reason": "自然な言いさし",
            },
            lambda *_: None,
            lambda: None,
        )

        self.assertEqual(result[0]["text"], self.segments[0]["text"])
        self.assertFalse(result[0]["recommended_review"]["llm"]["replacement_applied"])

    def test_recommended_cleanup_rejects_newly_echoed_instruction(self):
        def call(system, *_args):
            instruction = "話者が使った語尾と話し言葉を保ち、丁寧語や説明調に統一しません。"
            self.assertIn(instruction, system)
            return {"confirmed_problem": True, "needs_more_context": False,
                    "issue_type": "asr_error", "text": instruction, "reason": ""}

        result = finishing.repair_recommended_segments(
            self.segments, {"a": {"flagged": True}}, call,
            lambda *_: None, lambda: None,
        )
        self.assertEqual(result[0]["text"], self.segments[0]["text"])
        review = result[0]["recommended_review"]["llm"]
        self.assertFalse(review["replacement_applied"])
        self.assertIn("原文を保持", review["reason"])

    def test_recommended_cleanup_preserves_spoken_instruction_and_small_fix(self):
        spoken = "話者が使った語尾と話し言葉を保ち、丁寧語や説明調に統一しません"
        segment = {"id": "spoken", "speaker": "A", "text": spoken}
        result = finishing.repair_recommended_segments(
            [segment], {"spoken": {"flagged": True}},
            lambda *_: {"confirmed_problem": True, "needs_more_context": False,
                        "issue_type": "asr_error", "text": spoken + "。", "reason": "句点を補正"},
            lambda *_: None, lambda: None,
        )
        self.assertEqual(result[0]["text"], spoken + "。")
        self.assertTrue(result[0]["recommended_review"]["llm"]["replacement_applied"])

    def test_no_effort_keeps_original_without_calling_llm(self):
        calls = []
        result = finishing.repair_recommended_segments(
            self.segments, {"a": {"flagged": True}},
            lambda *_args: calls.append(True), lambda *_: None, lambda: None,
            effort="off",
        )
        self.assertEqual(calls, [])
        self.assertEqual(result, self.segments)

    def test_high_effort_expands_previous_context_one_at_a_time_up_to_ten(self):
        segments = [
            {"id": f"s{index}", "speaker": "A", "text": f"発話{index}"}
            for index in range(12)
        ]
        window_sizes = []

        def call(_system, prompt, _name, _schema):
            payload = json.loads(prompt.split('\n', 1)[1])
            window_sizes.append(len(payload["conversation_window"]))
            needs_more = len(window_sizes) < 10
            return {
                "confirmed_problem": not needs_more,
                "needs_more_context": needs_more,
                "issue_type": "asr_error" if not needs_more else "none",
                "text": "修正文" if not needs_more else "発話11",
                "reason": "前の会話から誤認識を確認" if not needs_more else "文脈不足",
            }

        result = finishing.repair_recommended_segments(
            segments, {"s11": {"flagged": True}}, call,
            lambda *_: None, lambda: None, effort="high", outline=self.outline,
        )

        self.assertEqual(window_sizes, list(range(2, 12)))
        self.assertEqual(result[-1]["text"], "修正文")
        self.assertEqual(result[-1]["recommended_review"]["llm"]["attempt_count"], 10)

    def test_max_effort_reads_outline_and_up_to_ten_turns_on_both_sides(self):
        segments = [
            {"id": f"s{index}", "speaker": "A", "text": f"発話{index}"}
            for index in range(25)
        ]
        captured = {}

        def call(_system, prompt, _name, _schema):
            captured.update(json.loads(prompt.split('\n', 1)[1]))
            return {"confirmed_problem": True, "needs_more_context": False,
                    "issue_type": "noise", "text": "予測した文章", "reason": "前後の流れから復元"}

        result = finishing.repair_recommended_segments(
            segments, {"s12": {"flagged": True}}, call,
            lambda *_: None, lambda: None, effort="ultra", outline=self.outline,
        )

        self.assertEqual(len(captured["conversation_window"]), 21)
        self.assertEqual(captured["outline"], self.outline["sections"])
        self.assertEqual(result[12]["text"], "予測した文章")
        self.assertEqual(result[12]["recommended_review"]["llm"]["effort"], "max")

    def test_full_long_single_utterance_id_and_boundary_preservation(self):
        segments = copy.deepcopy(self.segments)
        segments[0]['text'] = 'あ' * 1499 + ' ' + 'b' * 19000 + '末尾'
        calls = []
        def call(*args): calls.append(args[1]); return self.echo(*args)
        result = self.clean(call, segments)
        self.assertEqual(result, segments)
        self.assertGreater(len(calls), 1)
        self.assertIn('末尾', calls[-1])

    def test_missing_duplicate_reordered_or_empty_fragments_reject_all(self):
        for rows in ([], [{'id': 'unknown', 'text': 'yes'}],
                     [{'id': '1-0', 'text': 'b'}, {'id': '0-0', 'text': 'a'}],
                     [{'id': '0-0', 'text': ''}, {'id': '1-0', 'text': 'b'}]):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                self.clean(lambda *_: {'items': rows})
        self.assertEqual(self.segments[0]['text'], '賛成ではない。')

    def test_mid_call_failure_and_cancel_never_mutate_input(self):
        segments = copy.deepcopy(self.segments); segments[0]['text'] *= 4000
        before = copy.deepcopy(segments); calls = []
        def call(*args):
            calls.append(1)
            if len(calls) > 1: raise OSError('offline')
            return self.echo(*args)
        with self.assertRaises(OSError): self.clean(call, segments)
        self.assertEqual(segments, before)
        with self.assertRaises(InterruptedError):
            self.clean(self.echo, cancel=lambda: (_ for _ in ()).throw(InterruptedError()))

    def test_standalone_cleanup_builds_outline_before_revising(self):
        calls = []
        def call(system, prompt, name, schema):
            calls.append(name)
            if name == 'meeting_outline':
                return {'sections': [{'title': '検討', 'bullets': [
                    {'text': '検討する', 'segment_ids': ['b']}]}]}
            return self.echo(system, prompt, name, schema)
        result = finishing.clean_transcript(self.segments, call, lambda *_: None, lambda: None)
        self.assertEqual(calls, ['meeting_outline', 'transcript_cleanup'])
        self.assertEqual(result, self.segments)

    def test_every_batch_sees_global_outline_and_both_boundary_neighbors(self):
        segments = [{'id': f's-{i}', 'speaker': f'S{i % 2}', 'text': f'発話{i}' + '文脈' * 90} for i in range(95)]
        self.outline['sections'].append({'title': '最後の議題', 'bullets': ['来年度の計画']})
        payloads = []
        def call(*args):
            payloads.append(json.loads(args[1].split('\n', 1)[1]))
            return self.echo(*args)
        self.assertEqual(self.clean(call, segments), segments)
        self.assertGreater(len(payloads), 1)
        self.assertEqual([r['id'] for p in payloads for r in p['targets']],
                         [f'{i}-0' for i in range(len(segments))])
        for i, payload in enumerate(payloads):
            self.assertIn('来年度の計画', json.dumps(payload['outline'], ensure_ascii=False))
            if i:
                self.assertEqual(payload['context_before'], payloads[i - 1]['targets'][-2:])
            if i + 1 < len(payloads):
                self.assertEqual(payload['context_after'], payloads[i + 1]['targets'][:2])
        self.assertEqual(payloads[0]['context_before'], [])
        self.assertEqual(payloads[-1]['context_after'], [])

    def test_large_outline_reduction_reads_all_topics_and_cancels_between_calls(self):
        outline = {'sections': [{'title': f'議題{i}', 'bullets': ['説明' * 150]}
                                for i in range(100)]}
        seen = []
        def call(system, prompt, name, schema):
            batch = json.loads(prompt.split('\n', 1)[1])
            seen.extend(r['topic'] for r in batch)
            return {'summary': '、'.join(r['topic'] for r in batch)}
        context = finishing.outline_context(outline, call, lambda *_: None, lambda: None)
        self.assertEqual(seen, [f'議題{i}' for i in range(100)])
        self.assertIn('議題99', json.dumps(context, ensure_ascii=False))
        self.assertLessEqual(len(json.dumps(context, ensure_ascii=False)), 6000)
        def cancelled():
            if seen:
                raise InterruptedError()
        seen.clear()
        with self.assertRaises(InterruptedError):
            finishing.outline_context(outline, call, lambda *_: None, cancelled)
        self.assertLess(len(seen), 100)

    def test_noise_candidate_preserves_text_and_is_recorded_without_a_text_change(self):
        before = copy.deepcopy(self.segments)
        def call(*args):
            result = self.echo(*args)
            result['items'][0].update(text='AIが勝手に置き換えた本文', noise_candidate=True,
                                      reason='雑音を誤認識した疑い')
            return result
        result = self.clean(call)
        self.assertEqual(self.segments, before)
        self.assertEqual(result[0]['text'], before[0]['text'])
        self.assertEqual(result[0]['ai_review']['original_text'], before[0]['text'])
        self.assertTrue(result[0]['ai_review']['noise_candidate'])
        changes = finishing.finishing_changes(before, result)
        self.assertEqual(len(changes), 1)
        self.assertTrue(changes[0]['noise_candidate'])
        self.assertEqual(changes[0]['before_text'], changes[0]['after_text'])

    def test_full_cleanup_rejects_instruction_echo_per_fragment(self):
        def call(system, prompt, name, schema):
            result = self.echo(system, prompt, name, schema)
            result['items'][0].update(
                text='話者の口調や話し言葉を保ち、丁寧語への統一や説明調への書き換えをしません。',
                reason='',
            )
            result['items'][1].update(text='検討します！', reason='句読点の修正')
            return result

        result = self.clean(call)
        self.assertEqual(result[0]['text'], self.segments[0]['text'])
        self.assertTrue(result[0]['ai_review']['fragments'][0]['rejected_instruction'])
        self.assertIn('原文を保持', result[0]['ai_review']['fragments'][0]['reason'])
        self.assertEqual(result[1]['text'], '検討します！')

    def test_full_cleanup_keeps_spoken_instruction_quote(self):
        spoken = '話者の口調や話し言葉を保ち、丁寧語への統一や説明調への書き換えをしません'
        segments = [{'id': 'quoted', 'speaker': 'A', 'text': spoken}]
        def call(*args):
            result = self.echo(*args)
            result['items'][0].update(text=spoken + '。', reason='句点の修正')
            return result

        result = self.clean(call, segments)
        self.assertEqual(result[0]['text'], spoken + '。')

    def test_revision_keeps_original_and_invalid_decisions_reject_all(self):
        def corrected(*args):
            result = self.echo(*args)
            result['items'][1].update(text='検討します！', reason='句読点の修正')
            return result
        result = self.clean(corrected)
        self.assertEqual(result[1]['ai_review']['original_text'], '検討します。')
        self.assertFalse(result[1]['ai_review']['noise_candidate'])
        for bad in ({'noise_candidate': 'true'}, {'noise_candidate': True, 'reason': ''},
                    {'text': '変更したのに理由なし'}, {'reason': 'x' * 1001}):
            def call(*args):
                response = self.echo(*args)
                response['items'][0].update(bad)
                return response
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                self.clean(call)

    def test_rechecking_clears_old_noise_decisions_without_mutating_previous_version(self):
        segments = copy.deepcopy(self.segments)
        segments[0]['ai_review'] = {'noise_candidate': True, 'original_text': segments[0]['text']}
        result = self.clean(self.echo, segments)
        self.assertNotIn('ai_review', result[0])
        self.assertTrue(segments[0]['ai_review']['noise_candidate'])

    def test_outline_evidence_and_times_come_from_saved_source(self):
        result = finishing.create_outline(self.segments, {}, lambda *_: {'sections': [
            {'title': '検討', 'bullets': [{'text': '検討する', 'segment_ids': ['b', 'a']}]}]}, lambda *_: None, lambda: None)
        section = result['sections'][0]
        self.assertEqual((section['start'], section['end']), (2, 10))
        self.assertEqual(section['bullets'], ['検討する'])
        self.assertEqual(result['evidence']['a'], self.segments[0])
        self.assertEqual(result['provenance']['prompt_version'], finishing.FINISHING_VERSION)

    def test_outline_rejects_unknown_or_absent_evidence(self):
        for refs in ([], ['not-in-input'], ['a', 2]):
            with self.subTest(refs=refs), self.assertRaises(RuntimeError):
                finishing.create_outline(self.segments, {}, lambda *_: {'sections': [
                    {'title': '議題', 'bullets': [{'text': '要点', 'segment_ids': refs}]}]}, lambda *_: None, lambda: None)

    def test_outline_retries_once_for_an_out_of_batch_evidence_id(self):
        calls = []
        def call(*_):
            calls.append(1)
            refs = ['not-in-input'] if len(calls) == 1 else ['a']
            return {'sections': [{'title': '議題', 'bullets': [{'text': '要点', 'segment_ids': refs}]}]}
        result = finishing.create_outline(self.segments, {}, call, lambda *_: None, lambda: None)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['sections'][0]['segment_ids'], ['a'])

    def test_changes_require_exact_id_order_and_capture_speaker_repairs(self):
        after = copy.deepcopy(self.segments); after[0]['speaker'] = 'B'
        self.assertEqual(finishing.finishing_changes(self.segments, after)[0]['before_speaker'], 'A')
        with self.assertRaises(ValueError): finishing.finishing_changes(self.segments, after[::-1])
        self.assertEqual(finishing.clean_transcript([], self.echo, lambda *_: None, lambda: None), [])


if __name__ == '__main__':
    unittest.main()

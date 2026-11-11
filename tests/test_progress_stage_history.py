"""実DB・実モデルを使わず、工程履歴と公開境界を検証する。"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
source_root = Path(os.environ.get('GURUMOJI_STAGE_SOURCE_ROOT') or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(source_root / 'src'))
from gurumoji.runtime_state import RuntimeState
from functools import partial
from gurumoji.services.transcription_reporting import TranscriptionReporter
from gurumoji.services.transcription.job_record import JobRecord

class StageHistoryTests(unittest.TestCase):
    def reporter(self):
        record=JobRecord('synthetic','合成音声.wav',Path('/synthetic/output'),False,True)
        runtime=RuntimeState()
        JobRecord.state_lock=runtime.jobs_lock
        return record,TranscriptionReporter(record,partial(runtime.update_job,max_log_lines=50),runtime.jobs_lock,lambda x:x,lambda x,y:y)
    def test_completion_requires_stage_notification(self):
        job,r=self.reporter();r.stage('environment','環境確認',5);r.stage('preprocess','音声の前処理',10)
        self.assertEqual([x['status'] for x in job.stage_history],['pending','running'])
        r.stage('preprocess','音声の前処理',100);r.stage('environment','環境確認',100)
        self.assertTrue(all(x['status']=='completed' for x in job.stage_history))
    def test_repeated_pass_reopens_same_stage(self):
        job,r=self.reporter();r.stage('transcription','1回目',100);r.stage('transcription','2回目',10)
        self.assertEqual(len(job.stage_history),1);self.assertEqual(job.stage_history[0]['status'],'running')
        self.assertEqual(job.stage_history[0]['label'],'2回目')
    def test_failure_marks_interrupted_stage_only(self):
        job,r=self.reporter();r.stage('transcription','文字起こし',100);r.stage('diarization','話者の分離',40);r.stage('failed','エラー',40)
        self.assertEqual([x['status'] for x in job.stage_history],['completed','failed'])
        self.assertEqual(job.stage_history[-1]['label'],'話者の分離')
    def test_cancellation_keeps_completed_stage(self):
        job,r=self.reporter();r.stage('transcription','文字起こし',100);r.stage('cancelled','中止',100)
        self.assertEqual([x['status'] for x in job.stage_history],['completed','cancelled'])
    def test_completion_does_not_invent_unexecuted_stages(self):
        job,r=self.reporter();r.stage('transcription','文字起こし',100);r.stage('output','保存',75);r.stage('completed','完了',100)
        self.assertEqual([x['key'] for x in job.stage_history],['transcription','output'])
        self.assertTrue(all(x['status']=='completed' for x in job.stage_history))
    def test_public_snapshot_is_independent_and_sanitized(self):
        job, reporter = self.reporter()
        reporter.stage('transcription', '合成の工程', 10)
        with patch.object(JobRecord, 'reveal_local_paths', return_value=False):
            public = job.public()
            public['stage_history'][0]['status'] = 'completed'
            self.assertEqual(job.stage_history[0]['status'], 'running')
            self.assertEqual(public['stage_label'], '合成の工程')
            self.assertEqual(public['stage_history'][0]['label'], '合成の工程')
            for label in (r'C:\synthetic\private.wav', r'\\server\share\private.wav', '/synthetic/private.wav',
                          r'処理中 C:\synthetic\private.wav と /synthetic/private.wav'):
                with self.subTest(label=label):
                    reporter.stage('transcription', label, 30)
                    public = job.public()
                    self.assertEqual(public['stage_label'], '[local path hidden]')
                    self.assertEqual(public['stage_history'][0]['label'], '[local path hidden]')
                    self.assertEqual(job.stage_label, label)
        with patch.object(JobRecord, 'reveal_local_paths', return_value=True):
            self.assertEqual(job.public()['stage_label'], label)
            self.assertEqual(job.public()['stage_history'][0]['label'], label)
    def test_jobs_do_not_share_history(self):
        first,r=self.reporter();second,_=self.reporter();r.stage('output','保存',10)
        self.assertEqual(second.stage_history,[])

if __name__=='__main__':unittest.main()

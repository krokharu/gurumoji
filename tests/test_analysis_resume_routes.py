"""Explicit resume through real HTTP adapters; synthetic temporary app data."""
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import app
import browser_support
import test_analysis_milestones as support
from gurumoji.analysis_pipeline import AnalysisPipelineService, initialize_pipeline_store


class ResumeRouteTests(unittest.TestCase):
    setUp = support.AnalysisMilestoneTests.setUp
    payload = support.AnalysisMilestoneTests.payload
    status = support.AnalysisMilestoneTests.status
    wait = support.AnalysisMilestoneTests.wait

    def pending(self):
        with patch.object(AnalysisPipelineService, '_schedule'):
            response = self.client.post(self.url+'/pipelines', json=self.payload('resume-synthetic-request-0001'))
        self.assertEqual(response.status_code, 202, response.get_json())
        pid = response.get_json()['pipeline_id']
        with app.database_connection() as connection:
            initialize_pipeline_store(connection)
        return pid

    def dump(self):
        with app.database_connection() as connection:
            return list(connection.iterdump())

    def test_get_is_read_only_and_resume_uses_request_url(self):
        pid = self.pending(); before = self.dump()
        with patch.object(AnalysisPipelineService, '_schedule') as schedule:
            for _ in range(3):
                status = self.status(pid)
                self.assertEqual(status['allowed_actions'], ['resume'])
            schedule.assert_not_called()
            self.assertEqual(before, self.dump())
            response = self.client.post(self.url+'/pipelines/'+pid+'/resume', json={}, base_url='http://localhost:8123/')
            self.assertEqual(response.status_code, 200, response.get_json())
            schedule.assert_called_once_with(pid, 'http://localhost:8123/')
        app.analysis_pipeline_service()._run(pid, 'http://localhost:8123/')
        self.assertEqual(self.status(pid)['status'], 'completed')

    def test_resume_rejects_invalid_payload_wrong_owner_and_terminal_pipeline(self):
        pid = self.pending(); before = self.dump()
        route = self.url+'/pipelines/'+pid+'/resume'
        self.assertEqual(self.client.post(route, json=[]).status_code, 400)
        self.assertEqual(self.client.post(route.replace('/content/', '/other/'), json={}).status_code, 404)
        self.assertEqual(before, self.dump())
        self.client.post(self.url+'/pipelines/'+pid+'/cancel', json={})
        before = self.dump()
        for action in ('retry', 'resume'):
            response = self.client.post(self.url+'/pipelines/'+pid+'/'+action, json={})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.get_json()['reason_code'], 'pipeline_terminal')
        self.assertEqual(before, self.dump())


@browser_support.ui_browser_test
class ResumeBrowserTests(ResumeRouteTests):
    # Browser classes must not inherit and rerun the API tests.
    test_get_is_read_only_and_resume_uses_request_url = None
    test_resume_rejects_invalid_payload_wrong_owner_and_terminal_pipeline = None

    def test_restart_waits_without_polling_then_button_resumes_in_desktop_and_mobile(self):
        from playwright.sync_api import expect
        from werkzeug.serving import make_server
        pid = self.pending()
        before = self.dump()
        server = make_server('127.0.0.1', 0, app.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(thread.join, 5); self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        saved = {'id': pid, 'itemId': 'content', 'itemName': '架空の会話', 'mode': 'automatic', 'startedAt': 0}
        with patch.object(app, 'call_ai_json') as ai, browser_support.sandboxed_playwright_browser() as browser:
            page = browser.new_page(viewport={'width': 1360, 'height': 900})
            page.add_init_script('sessionStorage.setItem("gurumoji.analysisExecution.v2", '+json.dumps(json.dumps(saved))+');')
            gets = []
            page.on('request', lambda req: gets.append(req.url) if req.method == 'GET' and req.url.endswith('/pipelines/'+pid) else None)
            page.goto(f'http://127.0.0.1:{server.server_port}/#/analysis/content/run')
            # The existing analysis loader opens the workspace first. Re-enter
            # the persisted execution through its visible status control.
            expect(page.locator('#analysis-run-button')).to_have_text('実行状況を見る')
            page.locator('#analysis-run-button').click()
            resume = page.locator('#analysis-execution-review')
            expect(resume).to_be_visible(); expect(resume).to_have_text('固定入力から分析を再開')
            first = len(gets); page.wait_for_timeout(1200)
            self.assertEqual(len(gets), first)
            self.assertEqual(self.dump(), before)
            screenshots = Path(os.environ['MOJIOKOSI_UI_SCREENSHOT_DIR']) if os.environ.get('MOJIOKOSI_UI_SCREENSHOT_DIR') else None
            if screenshots:
                screenshots.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshots/'resume-desktop.png'), full_page=True)
            page.set_viewport_size({'width': 390, 'height': 844})
            expect(resume).to_be_visible()
            if screenshots:
                page.screenshot(path=str(screenshots/'resume-mobile.png'), full_page=True)
            with page.expect_response(lambda res: res.request.method == 'POST' and res.url.endswith('/resume')) as submitted:
                resume.click()
            self.assertEqual(submitted.value.status, 200)
            expect(page.locator('#analysis-execution-title')).to_contain_text('分析処理が完了', timeout=15000)
            expect(resume).to_be_hidden()
            self.assertEqual(self.status(pid)['status'], 'completed')
            self.assertEqual(self.status(pid)['generation'], 2)
            ai.assert_not_called()
            if screenshots:
                page.screenshot(path=str(screenshots/'resume-completed.png'), full_page=True)


if __name__ == '__main__':
    unittest.main()

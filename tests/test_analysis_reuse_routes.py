"""HTTP reuse and visible desktop/mobile flow, using only temporary app data."""
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


class ReuseRouteTests(unittest.TestCase):
    setUp=support.AnalysisMilestoneTests.setUp
    payload=support.AnalysisMilestoneTests.payload
    status=support.AnalysisMilestoneTests.status

    def accepted(self, request, **extra):
        with patch.object(AnalysisPipelineService,'_schedule'):
            response=self.client.post(self.url+'/pipelines',json={**self.payload(request),**extra})
        self.assertEqual(response.status_code,202,response.get_json())
        return response.get_json()['pipeline_id']

    def test_auto_none_and_read_only_status_through_http(self):
        with patch('gurumoji.services.group_analysis.utc_now_iso',return_value='2026-10-12T00:00:00Z'):
            old=self.accepted('http-reuse-synthetic-original')
        app.analysis_pipeline_service()._run(old,'http://synthetic.invalid')
        self.assertEqual(self.status(old)['status'],'completed')
        with patch.object(app,'run_analysis_pipeline_method',side_effect=AssertionError('reuse must skip method')), patch(
                'gurumoji.services.group_analysis.utc_now_iso',return_value='2026-10-13T00:00:00Z'):
            new=self.accepted('http-reuse-synthetic-auto')
            app.analysis_pipeline_service()._run(new,'http://synthetic.invalid')
        response=self.status(new)
        self.assertEqual(response['status'],'completed',response)
        reused=[s for m in response['milestones'] for s in m['steps'] if s['status']=='reused']
        self.assertEqual({s['step_id'] for s in reused},{'participation','conversation_dynamics'})
        with app.database_connection() as connection:
            before=list(connection.iterdump())
        self.status(new); self.status(new)
        with app.database_connection() as connection:
            self.assertEqual(before,list(connection.iterdump()))
        with patch.object(app,'run_analysis_pipeline_method',wraps=app.run_analysis_pipeline_method) as run:
            none=self.accepted('http-reuse-synthetic-none',reuse='none')
            app.analysis_pipeline_service()._run(none,'http://synthetic.invalid')
        self.assertEqual(self.status(none)['status'],'completed');self.assertEqual(run.call_count,2)


@browser_support.ui_browser_test
class ReuseBrowserTests(ReuseRouteTests):
    test_auto_none_and_read_only_status_through_http=None

    def test_resume_new_pipeline_displays_source_time_on_desktop_and_mobile(self):
        from playwright.sync_api import expect
        from werkzeug.serving import make_server
        old=self.accepted('browser-reuse-synthetic-original')
        app.analysis_pipeline_service()._run(old,'http://synthetic.invalid')
        self.assertEqual(self.status(old)['status'],'completed')
        pid=self.accepted('browser-reuse-synthetic-new')
        with app.database_connection() as connection:
            initialize_pipeline_store(connection)
        server=make_server('127.0.0.1',0,app.app,threaded=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(thread.join,5);self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        saved={'id':pid,'itemId':'content','itemName':'架空の会話','mode':'automatic','startedAt':0}
        with patch.object(app,'call_ai_json') as ai, patch.object(app,'run_analysis_pipeline_method',
                side_effect=AssertionError('reused method must not run')), browser_support.sandboxed_playwright_browser() as browser:
            page=browser.new_page(viewport={'width':1360,'height':900})
            page.add_init_script('sessionStorage.setItem("gurumoji.analysisExecution.v2",'+json.dumps(json.dumps(saved))+');')
            page.goto(f'http://127.0.0.1:{server.server_port}/#/analysis/content/run')
            expect(page.locator('#analysis-run-button')).to_have_text('実行状況を見る')
            page.locator('#analysis-run-button').click()
            resume=page.locator('#analysis-execution-review')
            expect(resume).to_have_text('固定入力から分析を再開')
            resume.click()
            expect(page.locator('#analysis-execution-title')).to_contain_text('分析処理が完了',timeout=15000)
            for name in ['participation','conversation_dynamics']:
                expect(page.locator(f'[data-reused-step="{name}"]')).to_contain_text('再利用（元の実行')
                self.assertNotIn('日時不明',page.locator(f'[data-reused-step="{name}"]').inner_text())
            shots=os.environ.get('MOJIOKOSI_UI_SCREENSHOT_DIR')
            if shots:
                Path(shots).mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(Path(shots)/'reuse-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            expect(page.locator('[data-reused-step="participation"]')).to_be_visible()
            for name in ['participation','conversation_dynamics']:
                self.assertTrue(page.locator(f'[data-reused-step="{name}"]').evaluate(
                    'node => getComputedStyle(node).whiteSpace === "normal" && node.scrollWidth <= node.clientWidth'))
            if shots:
                page.screenshot(path=str(Path(shots)/'reuse-mobile.png'),full_page=True)
            self.assertEqual(self.status(pid)['status'],'completed')
            ai.assert_not_called()


if __name__=='__main__':
    unittest.main()

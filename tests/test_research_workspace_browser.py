"""Opt-in actual Chromium interactions using a fictional database and Vault."""
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from werkzeug.serving import make_server
import app
import browser_support
import test_research_workspace as fixtures


@browser_support.ui_browser_test
class ResearchWorkspaceBrowserTests(unittest.TestCase):
    def test_fixed_statistics_preserve_source_without_ai(self):
        from playwright.sync_api import expect
        fixture=fixtures.ResearchWorkspaceTests('test_duplicate_frontmatter_is_rejected')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        rows=[{'unit':f'p{i}','value':i+(.5 if i%2 else 0),'condition':'A' if i<6 else 'B'} for i in range(12)]
        fixture.store.save(item_id='synthetic_a',kind='text_analysis',snapshot={'segments':[{'id':'u1','text':'架空の入力'}]},
            result={'parameters':{},'methods':[]},datasets={'values':(['unit','value','condition'],rows)},
            request_id='synthetic-statistics-browser',input_fingerprint='synthetic',source_revision=1,analysis_revision=1,publish=False)
        server=make_server('127.0.0.1',0,app.app,threaded=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(thread.join,5);self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        with patch.object(app,'call_ai_json') as ai,browser_support.sandboxed_playwright_browser() as browser:
            page=browser.new_page(viewport={'width':1440,'height':900});errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/#/analysis/synthetic_a',wait_until='networkidle')
            expect(page.locator('#analysis-item-select')).to_have_value('synthetic_a')
            page.locator('[data-analysis-mode="automatic"]:visible').first.click()
            expect(page.locator('#analysis-empty')).to_be_visible()
            page.get_by_role('button',name='保存履歴を更新',exact=True).click()
            page.locator('.analysis-archive-run summary').first.click()
            page.get_by_role('button',name='この保存済み結果を読む',exact=True).click()
            page.get_by_text('保存した表から統計を実行する',exact=True).click()
            form=page.locator('.analysis-fixed-body form').last
            def select_field(container,label,value):
                container.get_by_text(label,exact=True).locator('..').locator('select').select_option(value)
            select_field(form,'目的変数','value')
            select_field(form,'群・条件','condition')
            select_field(form,'話者・参加者を識別する列','unit')
            select_field(form,'手法','welch')
            select_field(form,'分析単位','participant')
            for column in ('value','condition','unit'):
                field=form.locator('fieldset').filter(has=page.locator('legend',has_text='変数：'+column))
                select_field(field,'値の出所','rule' if column=='value' else 'researcher')
                select_field(field,'尺度','ratio' if column=='value' else 'nominal')
            form.get_by_label('尺度・分析単位・変数の出所を確認しました',exact=True).check()
            form.get_by_role('button',name='統計を実行して別の固定結果に保存',exact=True).click()
            expect(form.locator('[role=status]')).to_contain_text('p=',timeout=15000)
            screenshot_root=Path(os.environ.get('GURUMOJI_WORKSPACE_SCREENSHOTS',fixture.root))
            screenshot_root.mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(screenshot_root/'statistics-desktop.png'))
            with fixture.store.connect() as db:
                saved=dict(db.execute("SELECT * FROM analysis_runs WHERE kind='planned_statistics'").fetchone())
            result=fixture.store.readable_package(saved['id'])[1]
            self.assertEqual(next(v for v in result['variable_catalog'] if v['column']=='value')['source'],'rule')
            self.assertTrue(all(v['validation_status']=='unvalidated' for v in result['variable_catalog']))
            ai.assert_not_called();self.assertFalse(errors,errors)

    def test_search_note_import_and_vault_preview_on_desktop_and_mobile(self):
        from playwright.sync_api import expect
        fixture=fixtures.ResearchWorkspaceTests('test_duplicate_frontmatter_is_rejected')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.note()
        server=make_server('127.0.0.1',0,app.app,threaded=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(thread.join,5);self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        with browser_support.sandboxed_playwright_browser() as browser:
            page=browser.new_page(viewport={'width':1440,'height':900})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            base=f'http://127.0.0.1:{server.server_port}'
            page.goto(base+'/#/data')
            page.locator('#cross-search-panel summary').click()
            page.locator('#cross-search-query').fill('窓口の説明')
            page.locator('#cross-search-form button').click()
            expect(page.locator('#cross-search-status')).to_contain_text('2件')
            page.locator('#cross-search-results a').first.click()
            page.locator('#item-tab-files').click()
            page.locator('#research-import-panel summary').click()
            page.locator('#research-notes-preview').click()
            expect(page.locator('#research-import-preview')).to_contain_text('synthetic-interpretation')
            page.get_by_role('button',name='選んだ差分を取り込む',exact=True).click()
            expect(page.locator('#research-import-status')).to_contain_text('履歴付きで取り込み')
            page.locator('#research-notes-history').click()
            expect(page.locator('#research-import-preview')).to_contain_text('独自タグ')
            screenshots=Path(os.environ.get('GURUMOJI_WORKSPACE_SCREENSHOTS',fixture.root))
            screenshots.mkdir(parents=True,exist_ok=True)
            page.locator('#research-import-panel').screenshot(path=str(screenshots/'research-import-desktop.png'))
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#research-notes-preview').click()
            expect(page.locator('#research-import-status')).to_contain_text('確認しました')
            page.screenshot(path=str(screenshots/'research-import-mobile.png'))
            page.goto(base+'/#/data')
            page.locator('#vault-tools-panel summary').click()
            page.locator('#vault-roots-load').click()
            expect(page.locator('#vault-roots-form')).to_be_visible()
            page.locator('#vault-roots-fields input[name=visualization]').fill('SyntheticBrowserVisuals')
            page.locator('#vault-roots-form button').click()
            expect(page.locator('#vault-tools-preview')).to_contain_text('SyntheticBrowserVisuals')
            self.assertFalse(errors,errors)

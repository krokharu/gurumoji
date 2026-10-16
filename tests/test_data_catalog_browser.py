"""Real browser actions against fictional data and a temporary SQLite database."""

import threading
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from werkzeug.serving import make_server

import app
import browser_support
import test_data_catalog as fixtures


@browser_support.ui_browser_test
class DataCatalogBrowserTests(unittest.TestCase):
    def test_create_bulk_assign_filter_preview_rename_remove_and_mobile(self):
        from playwright.sync_api import expect
        fixture = fixtures.DataCatalogTests('test_catalog_and_diagnostics_are_readonly_and_mutations_use_csrf')
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        server = make_server('127.0.0.1', 0, app.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(thread.join, 5); self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        with patch.object(app, 'call_ai_json') as llm, browser_support.sandboxed_playwright_browser() as browser:
            page = browser.new_page(viewport={'width': 1360, 'height': 900})
            page.route('**/api/ai/**', lambda route: route.fulfill(json={}))
            errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/#/data')
            page.locator('#manage-data-catalog-button').click()
            expect(page.locator('#data-catalog-dialog')).to_be_visible()
            page.locator('#data-tag-name').fill('2026年度')
            page.get_by_role('button', name='タグを作成', exact=True).click()
            expect(page.locator('#data-catalog-status')).to_have_text('タグを作成しました。')
            page.locator('#data-group-name').fill('研究集合')
            page.get_by_role('button', name='グループを作成', exact=True).click()
            expect(page.locator('#data-catalog-status')).to_have_text('分析グループを保存しました。')
            page.locator('#data-catalog-items input[value="a"]').check()
            page.locator('#data-catalog-items input[value="b"]').check()
            page.locator('#data-assignment').select_option(label='タグ: 2026年度')
            page.locator('#data-assign').click()
            expect(page.locator('#data-catalog-status')).to_have_text('2件の付与を保存しました。')
            page.locator('#data-assignment').select_option(label='グループ: 研究集合')
            page.locator('#data-assign').click()
            expect(page.locator('#data-catalog-items')).to_contain_text('分析グループ: 研究集合')
            page.locator('#data-group-name').fill('年度集合')
            page.locator('#data-group-kind').select_option('rule')
            page.locator('#data-rule-conditions select').first.select_option(label='タグ: 2026年度')
            page.locator('#data-rule-preview').click()
            expect(page.locator('#data-rule-preview-result')).to_contain_text('2件: 架空会話a、架空会話b')
            page.get_by_role('button', name='グループを作成', exact=True).click()
            expect(page.locator('#data-catalog-status')).to_have_text('分析グループを保存しました。')
            page.locator('#data-catalog-close').click()
            page.locator('#library-data-group').select_option(label='年度集合（2件）')
            expect(page.locator('#library-count')).to_have_text('2件を表示')
            expect(page.locator('#library-filter-summary')).to_contain_text('分析グループ: 年度集合')
            page.locator('#library-clear-filters').click()
            expect(page.locator('#library-count')).to_have_text('3件を表示')
            page.locator('#library-tag').select_option(label='2026年度（2件）')
            expect(page.locator('#library-count')).to_have_text('2件を表示')
            page.locator('#show-library-analysis-button').click()
            page.get_by_text('複数のグループインタビューを比較する', exact=True).click()
            page.locator('#interview-comparison-refresh').click()
            page.locator('#interview-comparison-data-group').select_option(label='研究集合（2件）')
            expect(page.locator('#interview-comparison-selection')).to_have_text('2件選択（2〜8件）')
            page.locator('#interview-comparison-run').click()
            expect(page.locator('#interview-comparison-result')).to_be_visible()
            page.get_by_role('button', name='比較結果を保存', exact=True).click()
            expect(page.locator('.interview-comparison-save-status')).to_contain_text('結果ファイルを保存しました')
            run = fixture.store.list_comparisons()[0]
            self.assertEqual(fixture.store.members(run['id']), ['a', 'b'])
            page.locator('#show-library-list-button').click()
            page.locator('#manage-data-catalog-button').click()
            page.get_by_text('名前・条件の変更と削除', exact=True).click()
            # Input value is a property, so select by its accessible name.
            field = page.get_by_role('textbox', name='年度集合の名前', exact=True)
            field.fill('改名集合')
            field.locator('..').get_by_role('button', name='名前を保存', exact=True).click()
            expect(page.get_by_role('textbox', name='改名集合の名前', exact=True)).to_be_visible()
            page.get_by_role('textbox', name='改名集合の名前', exact=True).locator('..').get_by_role('button', name='条件を編集', exact=True).click()
            page.locator('#data-rule-mode').select_option('any')
            page.locator('#data-rule-preview').click()
            expect(page.locator('#data-rule-preview-result')).to_contain_text('2件:')
            page.get_by_role('button', name='グループの条件を保存', exact=True).click()
            expect(page.locator('#data-catalog-status')).to_have_text('分析グループを保存しました。')
            page.locator('#data-assignment').select_option(label='タグ: 2026年度')
            page.locator('#data-unassign').click()
            expect(page.locator('#data-catalog-status')).to_have_text('2件の解除を保存しました。')
            expect(page.get_by_role('textbox', name='改名集合の名前').locator('..')).to_contain_text('0件')
            screenshot_dir = Path(os.environ.get('GURUMOJI_CATALOG_SCREENSHOT_DIR', fixture.root))
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            page.locator('#data-catalog-dialog').evaluate('el => el.scrollTop = 0')
            page.screenshot(path=str(screenshot_dir / 'catalog-desktop.png'))
            page.set_viewport_size({'width': 390, 'height': 844})
            page.locator('#data-catalog-dialog').evaluate('el => el.scrollTop = 0')
            expect(page.locator('#data-catalog-close')).to_be_visible()
            self.assertLessEqual(page.locator('#data-catalog-dialog').evaluate('el => el.scrollWidth - el.clientWidth'), 1)
            page.screenshot(path=str(screenshot_dir / 'catalog-mobile.png'))
            page.on('dialog', lambda d: d.accept())
            page.get_by_role('textbox', name='研究集合の名前').locator('..').get_by_role('button', name='削除', exact=True).click()
            expect(page.locator('#data-catalog-status')).to_contain_text('削除しました')
            self.assertEqual(errors, [])
            llm.assert_not_called()


if __name__ == '__main__':
    unittest.main()

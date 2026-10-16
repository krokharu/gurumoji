"""Opt-in verification of a separate main checkout without development assets."""
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import unittest

import app
from gurumoji.method_experts import ExpertCatalog
from gurumoji.services.analysis_slide_templates import load_slide_templates
import test_research_workspace as workspace_fixtures


@unittest.skipUnless(os.environ.get('GURUMOJI_MAIN_DELIVERY_ROOT'), 'not-run: select the separate main delivery checkout')
class MainDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main=Path(os.environ['GURUMOJI_MAIN_DELIVERY_ROOT']).resolve()
        cls.development=Path(__file__).resolve().parents[1]

    def test_main_does_not_track_tests_prototypes_or_development_tools(self):
        tracked=subprocess.check_output(['git','ls-files'],cwd=self.main,text=True).splitlines()
        rejected=[p for p in tracked if p.startswith(('tests/','devtools/','scratch/','output/','.agents/','.claude/'))
                  or p in {'pytest.ini','config/requirements-dev.txt','DESIGN.md','GEMINI.md','CLAUDE.md','run_knowledge_console.bat'}]
        self.assertEqual(rejected,[])

    def test_all_application_files_match_the_preserved_development_branch(self):
        paths=subprocess.check_output(['git','ls-files','src'],cwd=self.development,text=True).splitlines()
        self.assertGreater(len(paths),100)
        for name in paths:
            with self.subTest(path=name):
                self.assertEqual((self.main/name).read_bytes(),(self.development/name).read_bytes())

    def test_all_expert_knowledge_and_literature_remain_complete_and_identical(self):
        with TemporaryDirectory() as empty:
            main=ExpertCatalog(self.main/'docs/program-vault',empty)
            development=ExpertCatalog(self.development/'docs/program-vault',empty)
            self.assertEqual(set(main.index()),set(development.index()))
            self.assertEqual(len(main.index()),17)
            for eid in main.index():
                current=main.knowledge(eid,main.definition(eid))
                original=development.knowledge(eid,development.definition(eid))
                self.assertEqual(current['knowledge_hash'],original['knowledge_hash'],eid)
                self.assertFalse(current['missing_notes'],eid)
                self.assertFalse(current['missing_references'],eid)

    def test_slide_templates_validate_without_the_full_design_vault(self):
        current=load_slide_templates(self.main)
        self.assertTrue(current)
        self.assertEqual(current,load_slide_templates(self.development))

    def test_main_import_and_web_apis_use_only_main_resources(self):
        self.assertEqual(Path(app.PROJECT_DIRECTORY).resolve(),self.main)
        fixture=workspace_fixtures.ResearchWorkspaceTests('test_duplicate_frontmatter_is_rejected')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.assertEqual(fixture.client.get('/').status_code,200)
        listing=fixture.client.get('/api/library?limit=50&offset=0')
        self.assertEqual(listing.status_code,200)
        self.assertEqual(len(listing.get_json()['items']),2)
        result=fixture.client.get('/api/library/synthetic_a/analysis')
        self.assertEqual(result.status_code,200,result.get_json())
        methods=fixture.client.get('/api/library/synthetic_a/analysis/methods')
        self.assertEqual(methods.status_code,200,methods.get_json())
        self.assertGreater(len(methods.get_json()['methods']),15)

    def test_runtime_catalogue_hashes_are_current(self):
        vault=self.main/'docs/program-vault'
        manifest=json.loads((vault/'00-Catalog.json').read_text(encoding='utf-8'))
        import hashlib
        self.assertEqual(len(manifest['notes']),215)
        for note in manifest['notes']:
            self.assertEqual(hashlib.sha256((vault/note['path']).read_bytes()).hexdigest(),note['sha256'])

    def test_user_guide_local_links_resolve(self):
        guides=[self.main/'README.md',self.main/'AGENTS.md',*(self.main/'docs').glob('*.md')]
        for guide in guides:
            text=guide.read_text(encoding='utf-8')
            for link in re.findall(r'\]\(([^\s)]+)\)',text):
                if '://' in link or link.startswith(('#','mailto:')):continue
                with self.subTest(guide=guide.name,link=link):
                    self.assertTrue((guide.parent/link.split('#')[0]).exists())

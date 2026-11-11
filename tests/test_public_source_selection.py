"""公開版未指定・誤指定と、通常版packageの分離を検証する。"""
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from public_colab_source import load_public_module, public_source


class PublicSourceSelectionTests(unittest.TestCase):
    def test_unspecified_source_is_explicitly_not_run(self):
        with self.assertRaisesRegex(unittest.SkipTest, "not-run"):
            public_source(environ={})

    def test_explicit_missing_source_is_an_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "必要なファイル"):
                public_source("src/gurumoji/colab_support.py", environ={"GURUMOJI_COLAB_SOURCE": temporary})

    def test_public_relative_imports_do_not_replace_the_main_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "src/gurumoji"
            directory.mkdir(parents=True)
            (directory / "__init__.py").write_text("", encoding="utf-8")
            (directory / "colab_support.py").write_text("marker = '公開版の合成値'\n", encoding="utf-8")
            (directory / "colab_llm.py").write_text("from .colab_support import marker\n", encoding="utf-8")
            main = ModuleType("gurumoji")
            main.marker = "通常版の合成値"
            before = list(sys.path)
            previous = set(sys.modules)
            try:
                with patch.dict(sys.modules, {"gurumoji": main}):
                    public = load_public_module(root, "colab_llm")
                    self.assertEqual(public.marker, "公開版の合成値")
                    self.assertIs(sys.modules["gurumoji"], main)
                    self.assertEqual(sys.modules["gurumoji"].marker, "通常版の合成値")
                    self.assertEqual(sys.path, before)
                    self.assertTrue(Path(public.__file__).is_relative_to(root))
            finally:
                for name in set(sys.modules) - previous:
                    if name.startswith("_gurumoji_public_tests_"):
                        del sys.modules[name]

    def test_unapproved_module_name_is_rejected(self):
        with self.assertRaises(ValueError):
            load_public_module(Path.cwd(), "../private")

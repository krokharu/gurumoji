"""Windowsの既定文字コードでも、pipが日本語コメントをUTF-8で読めることを確認する。"""
from pathlib import Path
from unittest.mock import patch

import pytest
from pip._internal.utils import encoding


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = (
    "requirements-cloud-core.txt",
    "requirements-gurumoji-maf-dev.txt",
    "requirements-obussql-maf.txt",
    "requirements-obussql-metric.txt",
    "requirements-obussql.txt",
    "requirements.txt",
)


@pytest.mark.parametrize("filename", REQUIREMENTS)
def test_pip_decodes_requirements_as_utf8_under_cp932(filename):
    data = (ROOT / "config" / filename).read_bytes()
    assert data.splitlines()[0] == b"# -*- coding: utf-8 -*-"
    with patch.object(encoding.locale, "getpreferredencoding", return_value="cp932"):
        assert encoding.auto_decode(data) == data.decode("utf-8")


@pytest.mark.parametrize("filename", REQUIREMENTS)
def test_removing_encoding_cookie_reproduces_cp932_failure(filename):
    # 旧版と同じデータから宣言だけ除き、検査がUTF-8既定に依存していないことを確認する。
    data = (ROOT / "config" / filename).read_bytes()
    _, body = data.split(b"\n", 1)
    with patch.object(encoding.locale, "getpreferredencoding", return_value="cp932"):
        with pytest.raises(UnicodeDecodeError):
            encoding.auto_decode(body)

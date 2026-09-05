"""Test fixtures.

DATA_DIR is pointed at a fresh temporary directory before app.config is imported, so the
tests never touch real data, and it is wiped between tests.
"""
import os
import pathlib
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="trackwork-tests-")
os.environ["DATA_DIR"] = _TMP
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ENVIRONMENT"] = "development"
os.environ["SCHEDULER_ENABLED"] = "true"
for _k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "REPORT_EMAIL_RECIPIENT", "REPORT_EMAIL_SENDER"):
    os.environ.pop(_k, None)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def clean_data():
    for child in pathlib.Path(_TMP).iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    yield

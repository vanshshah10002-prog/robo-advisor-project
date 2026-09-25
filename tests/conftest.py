"""
Test setup: point the app at a throwaway SQLite database BEFORE any backend
module reads DATABASE_URL, so API tests never touch backend/data/portfolios.db.
"""

import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="robo-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP_DIR, 'test.db')}"

"""Run the full suite in disposable storage, preserving nested workspace fixtures."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from app import workspaces
    with tempfile.TemporaryDirectory() as folder,patch.object(workspaces,'ROOT',Path(folder)),patch.dict(os.environ):
        # An outer storage override would defeat tests that create their own ROOT.
        os.environ.pop('JAA_WORKSPACE_HOME',None)
        os.environ.pop('JAA_CANDIDATE_ID',None)
        suite=(unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:]) if len(sys.argv)>1
               else unittest.defaultTestLoader.discover(str(ROOT/'tests')))
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())

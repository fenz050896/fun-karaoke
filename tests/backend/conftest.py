import os
import sys
import tempfile
from pathlib import Path


_test_data = tempfile.TemporaryDirectory(prefix="fun-karaoke-tests-")
_previous_data_dir = os.environ.get("KARAOKE_DATA_DIR")
os.environ["KARAOKE_DATA_DIR"] = _test_data.name
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


def pytest_unconfigure(config):
    if _previous_data_dir is None:
        os.environ.pop("KARAOKE_DATA_DIR", None)
    else:
        os.environ["KARAOKE_DATA_DIR"] = _previous_data_dir
    _test_data.cleanup()

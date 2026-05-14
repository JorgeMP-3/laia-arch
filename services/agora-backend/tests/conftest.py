import os
import shutil
import tempfile

# Must run BEFORE any app imports
_test_dir = tempfile.mkdtemp(prefix="agora_test_")
os.environ["AGORA_ENV"] = "dev"
os.environ["AGORA_DATA_DIR"] = _test_dir
os.environ["AGORA_DEV_DATA_DIR"] = _test_dir

import atexit
atexit.register(lambda: shutil.rmtree(_test_dir, ignore_errors=True))

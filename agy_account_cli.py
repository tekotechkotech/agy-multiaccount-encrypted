import sys
from pathlib import Path

_repo_dir = str(Path(__file__).resolve().parent)
if _repo_dir not in sys.path:
    sys.path.insert(0, _repo_dir)

from agy_account_switch.agy_account_cli import *
from agy_account_switch.agy_account_cli import main

if __name__ == '__main__':
    main()

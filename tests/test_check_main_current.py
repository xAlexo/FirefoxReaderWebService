import subprocess
from pathlib import Path


def test_check_main_current_hook() -> None:
    script = Path(__file__).with_name('test_check_main_current.sh')
    subprocess.run(['bash', str(script)], check=True)

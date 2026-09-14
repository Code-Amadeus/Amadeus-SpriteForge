import subprocess
import sys


def cli(*args):
    return subprocess.run([sys.executable, "-m", "spriteforge", *map(str, args)], capture_output=True, text=True)


def test_demo_import_and_validate_without_amadeus(tmp_path):
    root = tmp_path / "my workspace"
    assert cli("init", root, "--demo").returncode == 0
    assert cli("validate-graph", "--workspace", root).returncode == 0
    assert cli("import", "--workspace", root, "--source", root / "projects/demo", "--name", "copy").returncode == 0
    assert len(list((root / "projects/copy").rglob("*.png"))) == 9
    assert cli("import", "--workspace", root, "--source", root / "projects/demo", "--name", "copy").returncode == 1
    assert cli("init", root, "--demo").returncode == 1

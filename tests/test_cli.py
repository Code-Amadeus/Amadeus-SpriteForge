import subprocess
import sys
import json

from spriteforge.production.records import load_owner


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


def test_production_crop_defaults_and_clip_settings_cli(studio):
    settings = ("production", "settings", "--workspace", studio.root)
    changed = cli(*settings, "--crop-black-border")
    assert changed.returncode == 0, changed.stderr
    assert json.loads(changed.stdout)["cropBlackBorder"] is True
    added = cli("production", "clip", "add", "--workspace", studio.root, "loop", "--from", "idle", "--to", "idle")
    assert added.returncode == 0, added.stderr
    assert load_owner(studio.root, "clip", "loop")["processing"]["cropBlackBorder"] is True
    disabled = cli(*settings, "--no-crop-black-border")
    assert disabled.returncode == 0, disabled.stderr
    assert json.loads(disabled.stdout)["cropBlackBorder"] is False
    assert load_owner(studio.root, "clip", "loop")["processing"]["cropBlackBorder"] is True
    command = ("production", "clip", "set", "--workspace", studio.root, "loop")
    result = cli(*command, "--no-crop-black-border", "--crop-black-threshold", 254, "--crop-black-margin", 0)
    assert result.returncode == 0, result.stderr
    processing = load_owner(studio.root, "clip", "loop")["processing"]
    assert (processing["cropBlackBorder"], processing["cropBlackThreshold"], processing["cropBlackMarginPx"]) == (False, 254, 0)
    path = studio.root / "production/clips/loop/clip.json"
    before = path.read_bytes()
    for option, value in (("--crop-black-threshold", 255), ("--crop-black-margin", -1)):
        assert cli(*command, option, value).returncode == 1
        assert path.read_bytes() == before

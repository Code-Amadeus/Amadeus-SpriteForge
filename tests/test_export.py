from pathlib import Path
from types import SimpleNamespace

import pytest

from spriteforge.character_pack import load_character_pack
from spriteforge.exporter import export_pack
from spriteforge.workspace import atomic_json, read_json


def fake_encoder(monkeypatch, fail_at=None):
    calls = []
    monkeypatch.setattr("spriteforge.exporter.shutil.which", lambda value: "test-encoder")
    def run(args, **kwargs):
        calls.append(args)
        if fail_at and len(calls) == fail_at:
            return SimpleNamespace(returncode=1, stderr="test encoding failure")
        Path(args[-2]).write_bytes(b"\xabKTX 20\xbb\r\n\x1a\n" + b"fixture")
        return SimpleNamespace(returncode=0, stderr="")
    monkeypatch.setattr("spriteforge.exporter.subprocess.run", run)
    return calls


def test_export_preserves_selected_variant_timing_and_graph(workspace, tmp_path, monkeypatch):
    calls = fake_encoder(monkeypatch)
    output = tmp_path / "pack"
    before = read_json(workspace / "graph_config.json")
    export_pack(workspace, output, pack_id="demo", display_name="Demo", version="1")
    pack = load_character_pack(output)
    assert pack.manifest["frameCount"] == 9
    assert pack.manifest["clips"]["idle"]["frameIntervalMs"] == 160
    assert [Path(c[-1]).name for c in calls[:3]] == ["0000.png", "0001.png", "0002.png"]
    assert calls[0][1:-2] == ["--t2", "--encode", "uastc", "--uastc_quality", "4", "--zcmp", "18",
                              "--target_type", "RGBA"]  # the shipped Amadeus packs' settings
    assert Path(calls[0][-1]).parent == workspace / before["nodes"][0]["root"]
    assert all("root" not in n and "x" not in n for n in pack.graph["nodes"])
    assert pack.graph["edges"] == before["edges"]
    assert read_json(workspace / "graph_config.json") == before
    companion = read_json(output.with_name("pack.graph-layout.json"))
    assert companion == {"nodes": [{k: n[k] for k in ("id", "label", "x", "y")} for n in before["nodes"]]}
    with pytest.raises(ValueError, match="already exists"):
        export_pack(workspace, output, pack_id="demo", display_name="Demo", version="1")


def test_encoder_failure_does_not_publish_partial_package(workspace, tmp_path, monkeypatch):
    fake_encoder(monkeypatch, fail_at=2)
    output = tmp_path / "pack"
    with pytest.raises(ValueError, match="encoding failed"):
        export_pack(workspace, output, pack_id="demo", display_name="Demo", version="1")
    assert not output.exists()
    assert not list(tmp_path.glob(".pack.*"))


def test_missing_encoder_and_mouth_config_are_explicit(workspace, tmp_path, monkeypatch):
    output = tmp_path / "pack"
    monkeypatch.setattr("spriteforge.exporter.shutil.which", lambda value: None)
    with pytest.raises(ValueError, match="toktx not found"):
        export_pack(workspace, output, pack_id="demo", display_name="Demo", version="1")
    atomic_json(workspace / "spriteforge_mouth_config.json", {"profiles": {"idle": {"root": "authoring"}}})
    fake_encoder(monkeypatch)
    with pytest.raises(ValueError, match="--no-mouth"):
        export_pack(workspace, output, pack_id="demo", display_name="Demo", version="1")
    export_pack(workspace, output, pack_id="demo", display_name="Demo", version="1", no_mouth=True)
    assert load_character_pack(output).mouth_config == {"expressions": {}, "profiles": {}}


def test_existing_layout_companion_is_not_overwritten(workspace, tmp_path):
    companion = tmp_path / "pack.graph-layout.json"
    companion.write_text("existing creator layout")
    with pytest.raises(ValueError, match="companion already exists"):
        export_pack(workspace, tmp_path / "pack", pack_id="demo", display_name="Demo", version="1")
    assert companion.read_text() == "existing creator layout"
    assert not (tmp_path / "pack").exists()

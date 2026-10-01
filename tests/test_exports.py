import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from synthetic import clip_with_take
from spriteforge.workspace import atomic_json, read_json
from spriteforge.production.exports import export_workspace, history, installed_diff, preflight, validate_version
from spriteforge.production.media import read_bgra, write_png
from spriteforge.production.project import graph_sync
from spriteforge.production.records import output_root
from spriteforge.production.render import render_clip
from spriteforge.production.tools import load_tools, save_tools


@pytest.fixture
def ready(studio, monkeypatch):
    clip_with_take(studio, "idle_loop", "idle", "idle", 8)
    render_clip(studio.root, "idle_loop", log=lambda *_: None)
    atomic_json(studio.root / "graph_config.json", {"nodes": [{"id": "idle", "label": "idle_loop", "isRoot": True,
                                                                "root": output_root("idle_loop"), "x": 50, "y": 80}], "edges": []})
    graph_sync(studio.root)
    calls = []
    monkeypatch.setattr("spriteforge.exporter.shutil.which", lambda _: "synthetic-encoder")

    def encode(args, **kwargs):
        calls.append(args)
        Path(args[-2]).write_bytes(b"\xabKTX 20\xbb\r\n\x1a\n" + hashlib.sha256(Path(args[-1]).read_bytes()).digest())
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("spriteforge.exporter.subprocess.run", encode)
    return studio, calls


def hashes(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def test_export_preflight_history_and_progress_share_real_encoding_facts(ready):
    studio, calls = ready
    result = preflight(studio.root)
    assert result["blockingCount"] == 0 and result["frameCount"] == 8
    assert result["durationEstimateS"] is None and result["encoding"] == {"uastc": 4, "zstd": 18}
    assert installed_diff(studio.root)["added"] == [{"label": "idle_loop", "clip": "idle_loop"}]
    messages = []
    exported = export_workspace(studio.root, "2026.10.02", notes="A local review build.", log=messages.append)
    output = studio.root / exported["output"]
    assert exported["frames"] == 8 and len(calls) == 8
    assert (output / "RELEASE_NOTES.md").read_text() == "A local review build."
    assert not list(output.rglob("*.png"))
    assert any("Encoded 8/8" in message for message in messages)
    [record] = history(studio.root)
    assert record["sourceHashes"]["idle_loop"] and record["textureHashes"]["idle_loop"]
    assert record["manifestSha256"] == hashlib.sha256((output / "runtime_manifest.json").read_bytes()).hexdigest()
    result = preflight(studio.root)
    assert result["history"][0]["version"] == "2026.10.02"
    assert result["durationEstimateS"] is not None and result["history"][0]["installed"] is False
    with pytest.raises(ValueError, match="already exists"):
        export_workspace(studio.root, "2026.10.02")
    assert len(calls) == 8


def test_texture_diff_is_unknown_until_encoded_and_never_writes_installed_pack(ready):
    studio, _ = ready
    exported = export_workspace(studio.root, "one", log=lambda *_: None)
    installed = studio.tmp / "installed"
    shutil.copytree(studio.root / exported["output"], installed)
    tools = load_tools(studio.root)
    tools["amadeus"] = {"packDir": str(installed)}
    save_tools(studio.root, tools)
    original = hashes(installed)
    diff = installed_diff(studio.root)
    assert all(diff[key] == [] for key in ("added", "updated", "removed", "unknown"))
    assert preflight(studio.root)["history"][0]["installed"] is True
    frame = studio.root / "production/clips/idle_loop/output/loop/000003.png"
    pixels = read_bgra(frame)[0]
    pixels[100:110, 100:110, 0] ^= 1
    write_png(frame, pixels)
    diff = installed_diff(studio.root)
    assert diff["updated"] == [] and diff["unknown"][0]["reason"] == "awaitingEncoding"
    export_workspace(studio.root, "two", log=lambda *_: None)
    diff = installed_diff(studio.root)
    assert [item["label"] for item in diff["updated"]] == ["idle_loop"] and diff["unknown"] == []
    assert hashes(installed) == original
    # An installed legacy pack without an authoring export match stays unknown.
    atomic_json(studio.root / "production/exports.json", {"format": "spriteforge.production.exports.v1", "exports": []})
    assert installed_diff(studio.root)["unknown"][0]["reason"] == "awaitingEncoding"


@pytest.mark.parametrize("version", ["../outside", "x/y", "x\\y", "", "name.", "C:/pack", None])
def test_export_version_cannot_escape_the_workspace(version):
    with pytest.raises(ValueError, match="version"):
        validate_version(version)


def test_export_rejects_installation_target_and_missing_encoder_without_creating_pack(ready, monkeypatch):
    studio, calls = ready
    destination = studio.root / "production/exports/forbidden"
    tools = load_tools(studio.root)
    tools["amadeus"] = {"packDir": str(destination)}
    save_tools(studio.root, tools)
    with pytest.raises(ValueError, match="installed pack"):
        export_workspace(studio.root, "forbidden")
    assert not destination.exists() and calls == []
    monkeypatch.setattr("spriteforge.exporter.shutil.which", lambda _: None)
    assert next(check for check in preflight(studio.root)["checks"] if check["id"] == "encoding")["level"] == "fail"
    with pytest.raises(ValueError, match="toktx"):
        export_workspace(studio.root, "missing-encoder")
    assert not (studio.root / "production/exports/missing-encoder").exists() and history(studio.root) == []

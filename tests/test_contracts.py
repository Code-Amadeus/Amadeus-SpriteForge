import copy
import json
from pathlib import Path

import pytest

from spriteforge.character_pack import CharacterPackError, _asset_path
from spriteforge.graph import layout_coordinates, runtime_graph, validate_graph
from spriteforge.workspace import atomic_json, clip_frames, discover, read_json, resolve_asset


def test_selected_frames_are_shared_by_preview_and_runtime_projection(workspace):
    graph = validate_graph(workspace, read_json(workspace / "graph_config.json"))
    root = next(n for n in graph["nodes"] if n["isRoot"])
    frames = clip_frames(workspace, root)
    assert [p.name for p in frames] == ["0000.png", "0001.png", "0002.png"]
    assert frames[0].parent == workspace / root["root"]
    assert "root" not in runtime_graph(graph)["nodes"][0]
    assert runtime_graph(graph)["edges"][0]["prob"] == 4
    assert len(discover(workspace)[0]["projects"][0]["states"]) == 3


@pytest.mark.parametrize("mutation", [
    lambda g: g["nodes"][1].update(isRoot=True),
    lambda g: g["nodes"][0].update(isRoot=False),
    lambda g: g["nodes"][1].update(id="idle"),
    lambda g: g["edges"][0].update(to="unknown"),
    lambda g: g["edges"].append({"id": "duplicate-pair", "from": "idle", "to": "idle", "prob": 1}),
    lambda g: g["edges"][0].update(prob=-1),
    lambda g: g["edges"][0].update(prob=float("nan")),
    lambda g: g["edges"][0].update(prob=True),
    lambda g: g["nodes"][0].update(frameIntervalMs=0),
    lambda g: g["nodes"][0].update(phase="../../outside"),
    lambda g: g["nodes"][0].update(root="missing"),
    lambda g: g["nodes"][1].update(label="idle"),
])
def test_invalid_authoring_graph_is_rejected(workspace, mutation):
    graph = read_json(workspace / "graph_config.json")
    original = copy.deepcopy(graph)
    mutation(graph)
    with pytest.raises(ValueError):
        validate_graph(workspace, graph)
    assert read_json(workspace / "graph_config.json") == original


def test_legacy_inside_workspace_absolute_paths_become_portable(workspace):
    graph = read_json(workspace / "graph_config.json")
    node = graph["nodes"][0]
    expected = node["root"]
    node["root"] = str(workspace / expected)
    del node["phase"]
    validated = validate_graph(workspace, graph)
    assert validated["nodes"][0]["root"] == expected
    assert validated["nodes"][0]["phase"] == "flat"


@pytest.mark.parametrize("path", ["../outside.png", "/etc/passwd", "C:/outside/file.png", "C:relative.png", "//server/share/frame.png"])
def test_cross_platform_paths_stay_inside_workspace(workspace, path):
    with pytest.raises(ValueError):
        resolve_asset(workspace, path)
    with pytest.raises(CharacterPackError):
        _asset_path(workspace, path, field="test")


def test_symlink_cannot_escape_workspace(workspace, tmp_path):
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"private")
    link = workspace / "linked.png"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation unavailable on this host")
    with pytest.raises(ValueError):
        resolve_asset(workspace, "linked.png")
    with pytest.raises(CharacterPackError):
        _asset_path(workspace, "linked.png", field="test")


def test_invalid_json_save_preserves_previous_file(workspace):
    path = workspace / "graph_config.json"
    before = path.read_bytes()
    with pytest.raises(ValueError):
        atomic_json(path, {"bad": float("nan")})
    assert path.read_bytes() == before


def test_layout_uses_exact_saved_id_label_and_coordinates(workspace):
    graph = read_json(workspace / "graph_config.json")
    runtime = runtime_graph(graph)
    positions = layout_coordinates(runtime, graph)
    assert positions["idle"] == {"x": 90, "y": 100}
    assert all("x" not in n for n in runtime["nodes"])
    graph["nodes"][0]["label"] = "different character"
    with pytest.raises(ValueError, match="identities"):
        layout_coordinates(runtime, graph)

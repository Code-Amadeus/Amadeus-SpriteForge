import json
import threading
import urllib.error
import urllib.request

import pytest

from spriteforge.server import make_server
from spriteforge.workspace import read_json


@pytest.fixture
def editor(workspace):
    server = make_server(workspace, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def request(editor, path, value=None, headers=None):
    content = None if value is None else json.dumps(value).encode()
    req = urllib.request.Request(editor + path, data=content, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        response = urllib.request.urlopen(req)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, response.read()


def test_editor_load_save_validate_and_exact_node_preview(editor, workspace):
    status, body = request(editor, "/")
    assert status == 200 and b"/static/review.js" in body
    assert request(editor, "/static/review.js")[0] == 200
    assert request(editor, "/api/projects")[0] == 200
    graph = read_json(workspace / "graph_config.json")
    graph["nodes"][0]["frameIntervalMs"] = 75
    graph["nodes"][0]["loopMode"] = "once_then_hold"
    assert request(editor, "/api/validate", graph)[0] == 200
    assert read_json(workspace / "graph_config.json")["nodes"][0]["frameIntervalMs"] == 160
    assert request(editor, "/api/graph", graph)[0] == 200
    status, body = request(editor, "/api/preview-node", {"graph": graph, "nodeId": "idle"})
    preview = json.loads(body)
    assert status == 200 and preview["node"]["frameIntervalMs"] == 75
    assert preview["node"]["loopMode"] == "once_then_hold"
    assert len(preview["frames"]) == 3
    assert request(editor, "/frame?path=" + preview["frames"][0])[1].startswith(b"\x89PNG")


def test_bad_save_and_foreign_origin_leave_graph_intact(editor, workspace):
    path = workspace / "graph_config.json"
    before = path.read_bytes()
    graph = read_json(path)
    assert request(editor, "/api/graph", graph, {"Origin": "https://example.com"})[0] == 403
    assert request(editor, "/api/graph", graph, {"Content-Type": "text/plain"})[0] == 403
    graph["nodes"][1]["isRoot"] = True
    assert request(editor, "/api/graph", graph)[0] == 400
    assert path.read_bytes() == before
    assert request(editor, "/frame?path=../secret.png")[0] == 400
    assert request(editor, "/frame?path=graph_config.json")[0] == 400


def test_qa_report_matches_ui_contract(editor, workspace):
    pytest.importorskip("cv2")
    root = read_json(workspace / "graph_config.json")["nodes"][0]["root"]
    status, body = request(editor, "/api/report?root=" + root)
    result = json.loads(body)
    assert status == 200 and result["ok"]
    assert result["report"]["summary"]["clip_count"] == 1


def test_runtime_pack_is_manifest_indexed_and_read_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "examples/runtime-minimal"
    graph_before = (root / "graph_config.json").read_bytes()
    server = make_server(root, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        status, body = request(url, "/api/projects")
        assert status == 200 and json.loads(body)["readOnly"]
        status, body = request(url, "/api/graph")
        assert status == 200
        assert json.loads(body)["layoutAvailable"]
        assert json.loads(body)["graph"]["nodes"][0]["x"] == 90
        assert request(url, "/api/graph", {})[0] == 409
        status, body = request(url, "/api/preview-node", {"nodeId": "idle"})
        preview = json.loads(body)
        assert status == 200 and preview["node"]["frameIntervalMs"] == 160
        assert request(url, "/frame?path=" + preview["frames"][0])[1].startswith(b"\xabKTX 20")
        assert request(url, "/frame?path=runtime_manifest.json")[0] == 400
        assert request(url, "/api/report?root=idle")[0] == 400
        assert request(url, "/static/vendor/basis_transcoder.wasm")[0] == 200
        assert (root / "graph_config.json").read_bytes() == graph_before
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_pack_without_layout_does_not_invent_coordinates(tmp_path):
    import shutil
    from pathlib import Path
    root = tmp_path / "pack"
    shutil.copytree(Path(__file__).resolve().parents[1] / "examples/runtime-minimal", root)
    server = make_server(root, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        status, body = request(url, "/api/graph")
        response = json.loads(body)
        assert status == 200 and response["layoutAvailable"] is False
        assert all("x" not in n and "y" not in n for n in response["graph"]["nodes"])
        assert request(url, "/api/clips?root=idle")[0] == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

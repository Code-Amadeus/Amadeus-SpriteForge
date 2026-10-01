import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")

from synthetic import frame_folder, provider_frames, still, write_video  # noqa: E402

from spriteforge.production.clips import import_clip_take, prepare  # noqa: E402
from spriteforge.production.project import add_clip, set_clip  # noqa: E402
from spriteforge.production.records import load_owner  # noqa: E402
from spriteforge.server import make_server  # noqa: E402


@pytest.fixture
def editor(studio):
    server = make_server(studio.root, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def call(url, path, body=None, *, raw=None, content_type="application/json", headers=None):
    data = raw if raw is not None else None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url + path, data=data, headers={"Content-Type": content_type, **(headers or {})})
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        payload = response.read()
        return response.status, (json.loads(payload) if response.headers.get_content_type() == "application/json" else payload), response.headers


def test_page_overview_decisions_and_prompt_versions(editor, studio):
    status, page, _ = call(editor, "/production")
    assert status == 200 and b"/static/production.js" in page
    assert call(editor, "/static/production.js")[0] == 200
    add_clip(studio.root, "smile_in", "idle", "smile")
    take = import_clip_take(studio.root, "smile_in", frame_folder(studio, "t", "idle", "smile", 20), fps=30)
    status, state, _ = call(editor, "/api/production")
    assert status == 200 and state["initialized"] and [p["id"] for p in state["poses"]] == ["idle", "smile"]
    assert state["clips"][0]["promptPreview"]["complete"] is False
    assert call(editor, "/api/production/decision", {"kind": "clip", "owner": "smile_in", "take": take["id"], "action": "accept"})[0] == 200
    assert load_owner(studio.root, "clip", "smile_in")["acceptedTake"] == take["id"]
    status, result, _ = call(editor, "/api/production/prompt", {"block": "character", "text": "Demo girl, ${character}"})
    assert status == 200 and result["version"] == 2
    status, result, _ = call(editor, "/api/production/decision", {"kind": "clip", "owner": "smile_in", "take": "bad", "action": "accept"})
    assert status == 400 and "Invalid take id" in result["error"]
    assert call(editor, "/api/production/unknown", {})[0] == 404


def test_canvas_positions_and_generator_inputs(editor, studio):
    assert call(editor, "/static/production-canvas.js")[0] == 200
    assert call(editor, "/api/production")[1]["canvas"] == {}
    status, result, _ = call(editor, "/api/production/canvas", {"positions": {"pose:idle": [10, 20.26], "pose:smile": [300, -40]}})
    saved = {"pose:idle": [10.0, 20.3], "pose:smile": [300.0, -40.0]}
    assert status == 200 and result["positions"] == saved
    for bad in ({"node:idle": [0, 0]}, {"pose:Bad": [0, 0]}, {"pose:idle": [0]}, {"pose:idle": [True, 0]},
                {"pose:idle": [float("nan"), 0]}, ["pose:idle"]):
        assert call(editor, "/api/production/canvas", {"positions": bad})[0] == 400, bad
    assert call(editor, "/api/production")[1]["canvas"] == saved

    add_clip(studio.root, "smile_in", "idle", "smile")
    status, first, headers = call(editor, "/api/production/input?clip=smile_in&end=first")
    assert status == 200 and headers.get_content_type() == "image/png"
    prepare(studio.root, "clip", "smile_in", studio.tmp / "handoff")
    assert first == (studio.tmp / "handoff" / "first.png").read_bytes()
    set_clip(studio.root, "smile_in", last_frame="none")
    status, result, _ = call(editor, "/api/production/input?clip=smile_in&end=last")
    assert status == 400 and "first frame only" in result["error"]
    assert call(editor, "/api/production/input?clip=smile_in&end=middle")[0] == 400


def test_uploads_media_ranges_and_render_job(editor, studio):
    add_clip(studio.root, "smile_in", "idle", "smile")
    video = write_video(studio.tmp / "upload.mp4", provider_frames(still(studio, "idle"), still(studio, "smile"), 20)).read_bytes()
    status, result, _ = call(editor, "/api/production/upload?kind=clip&owner=smile_in&name=take.mp4", raw=video,
                             content_type="application/octet-stream")
    assert status == 200 and result["take"]["media"]["count"] == 20
    take_id = result["take"]["id"]
    media = f"/api/production/media?path=production/clips/smile_in/takes/{take_id}/media.mp4"
    status, body, headers = call(editor, media, headers={"Range": "bytes=0-99"})
    assert status == 206 and len(body) == 100 and headers["Content-Range"].endswith(f"/{len(video)}")
    assert call(editor, "/api/production/media?path=production/clips/smile_in/clip.json")[0] == 400
    assert call(editor, "/api/production/media?path=graph_config.json")[0] == 400
    assert call(editor, "/api/production/media?path=../x.png")[0] == 400
    assert call(editor, "/api/production/upload?kind=clip&owner=smile_in&name=a.mp4", raw=b"x",
                content_type="application/json")[0] == 403
    call(editor, "/api/production/decision", {"kind": "clip", "owner": "smile_in", "take": take_id, "action": "accept"})
    status, result, _ = call(editor, "/api/production/jobs", {"action": "render", "clip": "smile_in"})
    assert status == 200 and result["job"]["status"] == "running"
    for _ in range(300):
        jobs = call(editor, "/api/production/jobs")[1]["jobs"]
        if jobs[0]["status"] != "running":
            break
        time.sleep(0.1)
    assert jobs[0]["status"] == "succeeded", jobs[0]
    state = call(editor, "/api/production")[1]
    assert state["clips"][0]["render"]["state"] == "current"


def test_foreign_origin_and_runtime_packs_cannot_use_production(editor):
    status, _, _ = call(editor, "/api/production/prompt", {"block": "character", "text": "x"}, headers={"Origin": "https://example.com"})
    assert status == 403
    pack = Path(__file__).resolve().parents[1] / "examples/runtime-minimal"
    server = make_server(pack, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        assert call(url, "/api/production")[0] == 409
        assert call(url, "/api/production/prompt", {"block": "character", "text": "x"})[0] == 409
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

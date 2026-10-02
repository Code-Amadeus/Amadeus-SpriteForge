"""Studio shares local authority and records with the legacy production page."""
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import pytest

from spriteforge.server import make_server


@pytest.fixture
def studio_server(studio):
    server = make_server(studio.root, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def request(url, path, body=None, **headers):
    req = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    try:
        response = urllib.request.urlopen(req)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        payload = response.read()
        return response.status, json.loads(payload) if response.headers.get_content_type() == "application/json" else payload


def test_production_entry_points_open_studio(studio_server):
    for route, script in (("/", b"studio.js"), ("/production", b"studio.js"), ("/studio", b"studio.js")):
        status, content = request(studio_server, route)
        assert status == 200 and script in content
    for asset in ("studio.css", "studio.js", "studio-tools.js", "i18n/en.js", "i18n/zh-CN.js"):
        assert request(studio_server, "/static/" + asset)[0] == 200
    assert request(studio_server, "/static/i18n/../../production/tools.json")[0] == 404
    assert request(studio_server, "/studio", Host="evil.test")[0] == 403

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_):
            return None

    for route in ("/", "/production"):
        with pytest.raises(urllib.error.HTTPError) as redirect:
            urllib.request.build_opener(NoRedirect).open(studio_server + route)
        assert redirect.value.code == 302 and redirect.value.headers["Location"] == "/studio"


def test_settings_shared_with_overview_and_origin_checked(studio_server, studio):
    changes = {"stillProvider": "seedream", "conceptProvider": "qwen-image", "batchConfirmThreshold": 4}
    assert request(studio_server, "/api/production/tools-settings", {"defaults": changes})[0] == 200
    assert request(studio_server, "/api/production")[1]["tools"]["defaults"] == {**changes, "cropBlackBorder": False}
    path = studio.root / "production" / "tools.json"
    before = path.read_bytes()
    for invalid in ({"command": ["evil"]}, {"stillProvider": "wan"}, {"batchConfirmThreshold": True},
                    {"batchConfirmThreshold": 0}, {"cropBlackBorder": "false"}, {"cropBlackBorder": 1}):
        assert request(studio_server, "/api/production/tools-settings", {"defaults": invalid})[0] == 400
        assert path.read_bytes() == before
    assert request(studio_server, "/api/production/tools-settings", {"defaults": changes}, Origin="https://example.com")[0] == 403


def test_crop_settings_http_share_creation_and_validation_boundaries(studio_server, studio):
    from spriteforge.production.project import add_clip

    add_clip(studio.root, "before", "idle", "idle")
    assert request(studio_server, "/api/production/tools-settings", {"defaults": {"cropBlackBorder": True}})[0] == 200
    add_clip(studio.root, "after", "idle", "idle")
    clips = {clip["id"]: clip for clip in request(studio_server, "/api/production")[1]["clips"]}
    assert clips["before"]["processing"]["cropBlackBorder"] is False
    assert clips["after"]["processing"]["cropBlackBorder"] is True
    changes = {"crop_black_border": False, "crop_black_threshold": 0, "crop_black_margin": 0}
    status, result = request(studio_server, "/api/production/clip-settings", {"clip": "after", "changes": changes})
    assert status == 200 and result["clip"]["processing"]["cropBlackBorder"] is False
    path = studio.root / "production/clips/after/clip.json"
    before = path.read_bytes()
    for invalid in ({"crop_black_border": "false"}, {"crop_black_threshold": True}, {"crop_black_threshold": 255},
                    {"crop_black_margin": 1.5}, {"crop_black_margin": -1}):
        assert request(studio_server, "/api/production/clip-settings", {"clip": "after", "changes": invalid})[0] == 400
        assert path.read_bytes() == before


def test_settings_cli_reads_without_writing_and_uses_same_contract(studio):
    path = studio.root / "production" / "tools.json"
    before = path.read_bytes()
    args = [sys.executable, "-m", "spriteforge", "production", "settings", "--workspace", str(studio.root)]
    shown = subprocess.run(args, capture_output=True, text=True)
    assert shown.returncode == 0, shown.stderr
    assert json.loads(shown.stdout)["batchConfirmThreshold"] == 3
    assert path.read_bytes() == before
    changed = subprocess.run([*args, "--still-provider", "seedream"], capture_output=True, text=True)
    assert changed.returncode == 0, changed.stderr
    assert json.loads(path.read_text())["defaults"]["stillProvider"] == "seedream"

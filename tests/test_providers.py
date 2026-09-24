import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

cv2 = pytest.importorskip("cv2")

from synthetic import provider_frames, still, write_video  # noqa: E402

from spriteforge.production import prompts  # noqa: E402
from spriteforge.production.clips import generate_clip_take, resume_clip_take  # noqa: E402
from spriteforge.production.project import add_clip, set_clip  # noqa: E402
from spriteforge.production.records import list_takes, load_take, take_dir  # noqa: E402
from spriteforge.production.tools import load_tools, save_tools  # noqa: E402


class FakeProviders:
    """Local stand-in for the Wan (DashScope) and Seedance (Ark) task APIs."""

    def __init__(self, video: bytes):
        self.video, self.requests, self.polls, self.fail = video, [], 0, False
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def reply(self, value: dict) -> None:
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append(("POST", self.path, {k.lower(): v for k, v in self.headers.items()}, body))
                self.reply({"output": {"task_id": "wan-1", "task_status": "PENDING"}} if "video-synthesis" in self.path
                           else {"id": "cgt-1"})

            def do_GET(self):
                fake.requests.append(("GET", self.path, {k.lower(): v for k, v in self.headers.items()}, None))
                if self.path == "/result.mp4":
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(fake.video)))
                    self.end_headers()
                    self.wfile.write(fake.video)
                    return
                fake.polls += 1
                done = fake.polls >= 2
                url = f"http://127.0.0.1:{fake.port}/result.mp4"
                if "/api/v1/tasks/" in self.path:
                    status = "FAILED" if fake.fail else "SUCCEEDED" if done else "RUNNING"
                    self.reply({"output": {"task_id": "wan-1", "task_status": status, "video_url": url,
                                           "message": "content check"}})
                else:
                    status = "failed" if fake.fail else "succeeded" if done else "running"
                    self.reply({"id": "cgt-1", "status": status, "content": {"video_url": url},
                                "error": {"message": "content check"}})

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def providers(studio, monkeypatch):
    frames = provider_frames(still(studio, "idle"), still(studio, "smile"), 24)
    fake = FakeProviders(write_video(studio.tmp / "result.mp4", frames).read_bytes())
    tools = load_tools(studio.root)
    for name, path in (("wan", "/api/v1"), ("seedance", "/api/v3")):
        tools["providers"][name].update(baseUrl=f"http://127.0.0.1:{fake.port}{path}", pollSeconds=0.01)
    save_tools(studio.root, tools)
    add_clip(studio.root, "smile_in", "idle", "smile")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "wan-secret")
    monkeypatch.setenv("ARK_API_KEY", "ark-secret")
    yield fake
    fake.server.shutdown()
    fake.server.server_close()


def write_prompts(studio):
    library = prompts.load_library(studio.root)
    for block_id in library["blocks"]:
        prompts.set_block(library, block_id, f"{block_id}: ${{character}}" if block_id == "character" else f"{block_id} text")
    prompts.save_library(studio.root, library)


def test_placeholders_never_reach_a_paid_provider(studio, providers):
    set_clip(studio.root, "smile_in", provider="wan")
    with pytest.raises(ValueError, match="placeholder"):
        generate_clip_take(studio.root, "smile_in", log=lambda *_: None)
    assert providers.requests == [] and list_takes(studio.root, "clip", "smile_in") == []
    preview = generate_clip_take(studio.root, "smile_in", dry_run=True)
    assert preview["request"]["input"]["media"][0]["url"].startswith("<first.png sha256=")
    assert preview["prompt"]["complete"] is False and providers.requests == []


def test_wan_request_polling_and_download(studio, providers):
    write_prompts(studio)
    set_clip(studio.root, "smile_in", provider="wan", duration=3, seed=11)
    take = generate_clip_take(studio.root, "smile_in", log=lambda *_: None)
    method, path, headers, body = providers.requests[0]
    assert (method, path) == ("POST", "/api/v1/services/aigc/video-generation/video-synthesis")
    assert headers["authorization"] == "Bearer wan-secret" and headers["x-dashscope-async"] == "enable"
    assert [m["type"] for m in body["input"]["media"]] == ["first_frame", "last_frame"]
    assert all(m["url"].startswith("data:image/png;base64,") for m in body["input"]["media"])
    assert body["input"]["negative_prompt"] == "video.negative text"
    assert body["parameters"] == {"resolution": "720P", "duration": 3, "prompt_extend": False, "watermark": False, "seed": 11}
    assert body["model"] == "wan2.7-i2v-2026-04-25" and body["input"]["prompt"].startswith("character: Demo")
    assert (take["state"], take["source"]["taskId"], take["media"]["count"]) == ("ready", "wan-1", 24)
    assert take["prompt"]["negativeSent"] and take["inputs"]["first"]["pose"] == "idle"
    directory = take_dir(studio.root, "clip", "smile_in", take["id"])
    assert {p.name for p in directory.iterdir()} == {"take.json", "first.png", "last.png", "media.mp4"}
    assert "wan-secret" not in (directory / "take.json").read_text(encoding="utf-8")


def test_seedance_request_and_recorded_failure(studio, providers):
    write_prompts(studio)
    set_clip(studio.root, "smile_in", provider="seedance")
    take = generate_clip_take(studio.root, "smile_in", wait=False)
    _, path, headers, body = providers.requests[0]
    assert path == "/api/v3/contents/generations/tasks" and headers["authorization"] == "Bearer ark-secret"
    assert [c.get("role") for c in body["content"]] == [None, "first_frame", "last_frame"]
    assert (body["ratio"], body["resolution"], body["generate_audio"]) == ("adaptive", "720p", False)
    assert take["state"] == "submitted" and take["prompt"]["negativeSent"] is False
    providers.fail = True
    with pytest.raises(ValueError, match="content check"):
        resume_clip_take(studio.root, "smile_in", take["id"], log=lambda *_: None)
    failed = load_take(studio.root, "clip", "smile_in", take["id"])
    assert failed["state"] == "failed" and "content check" in failed["error"]


def test_resume_after_submission_and_missing_key(studio, providers, monkeypatch):
    write_prompts(studio)
    set_clip(studio.root, "smile_in", provider="wan")
    take = generate_clip_take(studio.root, "smile_in", wait=False)
    ready = resume_clip_take(studio.root, "smile_in", take["id"], log=lambda *_: None)
    assert ready["state"] == "ready" and ready["media"]["fps"] == 30
    monkeypatch.delenv("DASHSCOPE_API_KEY")
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        generate_clip_take(studio.root, "smile_in")
    assert len(list_takes(studio.root, "clip", "smile_in")) == 1

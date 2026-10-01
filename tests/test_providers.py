import base64
import hashlib
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

cv2 = pytest.importorskip("cv2")

import numpy as np  # noqa: E402
from synthetic import CANVAS, PROCESSORS, flatten, mouth_centre, provider_frames, still, write_video  # noqa: E402

from spriteforge.production import prompts  # noqa: E402
from spriteforge.production.api import ProductionApi  # noqa: E402
from spriteforge.production.clips import generate_clip_take, resume_clip_take  # noqa: E402
from spriteforge.production.project import add_clip, add_pose, overview, set_clip  # noqa: E402
from spriteforge.production.records import list_takes, load_take, take_dir  # noqa: E402
from spriteforge.production.stills import approve_still, generate_still  # noqa: E402
from spriteforge.production.tools import load_tools, save_tools  # noqa: E402

IMAGE_PATHS = ("/api/v1/services/aigc/multimodal-generation/generation", "/api/v3/images/generations")


class FakeProviders:
    """Local stand-in for the DashScope (Wan, Qwen image edit) and Ark (Seedance, Seedream) APIs."""

    def __init__(self, video: bytes):
        self.video, self.requests, self.polls, self.fail = video, [], 0, False
        self.edited, self.image_error = b"", None
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def reply(self, value: dict, status: int = 200) -> None:
                body = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append(("POST", self.path, {k.lower(): v for k, v in self.headers.items()}, body))
                if self.path in IMAGE_PATHS and fake.image_error:
                    self.reply({"code": "DataInspectionFailed", "message": fake.image_error}, 400)
                elif self.path == IMAGE_PATHS[0]:
                    url = f"http://127.0.0.1:{fake.port}/edit.png"
                    self.reply({"output": {"choices": [{"message": {"role": "assistant", "content": [{"image": url}]}}]}})
                elif self.path == IMAGE_PATHS[1]:
                    self.reply({"data": [{"b64_json": base64.b64encode(fake.edited).decode()}]})
                else:
                    self.reply({"output": {"task_id": "wan-1", "task_status": "PENDING"}} if "video-synthesis" in self.path
                               else {"id": "cgt-1"})

            def do_GET(self):
                fake.requests.append(("GET", self.path, {k.lower(): v for k, v in self.headers.items()}, None))
                if self.path in ("/result.mp4", "/edit.png"):
                    data = fake.video if self.path == "/result.mp4" else fake.edited
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
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
    for name, path in (("wan", "/api/v1"), ("seedance", "/api/v3"), ("qwen-image", "/api/v1"), ("seedream", "/api/v3")):
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


def test_first_frame_only_requests(studio, providers):
    add_pose(studio.root, "bow")
    add_clip(studio.root, "bow_in", "idle", "bow")
    write_prompts(studio)
    set_clip(studio.root, "bow_in", provider="wan", last_frame="none")
    take = generate_clip_take(studio.root, "bow_in", wait=False)
    body = providers.requests[0][3]
    assert [m["type"] for m in body["input"]["media"]] == ["first_frame"]
    assert take["inputs"] == {"first": {**take["inputs"]["first"], "pose": "idle", "file": "first.png"}, "last": None}
    assert {p.name for p in take_dir(studio.root, "clip", "bow_in", take["id"]).iterdir()} == {"take.json", "first.png"}
    set_clip(studio.root, "bow_in", provider="seedance")
    assert [c.get("role") for c in generate_clip_take(studio.root, "bow_in", dry_run=True)["request"]["content"]] == \
        [None, "first_frame"]
    generate_clip_take(studio.root, "bow_in", wait=False)
    assert [c.get("role") for c in providers.requests[-1][3]["content"]] == [None, "first_frame"]


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


def edited_still(studio, encoding: str = ".png") -> bytes:
    """What an image editor returns: the base still with a new mouth, opaque, at twice the size and nudged."""
    image = still(studio, "idle").copy()
    mx, my = mouth_centre(studio)
    cv2.rectangle(image, (mx - 8, my - 2), (mx + 8, my + 5), (40, 40, 150, 255), -1)
    flat = cv2.resize(flatten(image), None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    moved = cv2.warpAffine(flat, np.float32([[1, 0, 6], [0, 1, -4]]), flat.shape[1::-1], borderValue=(255, 255, 255))
    return cv2.imencode(encoding, moved)[1].tobytes()


def quiet(*_):
    pass


def test_qwen_image_edit_becomes_a_normalised_still(studio, providers):
    add_pose(studio.root, "grin", "wide grin")
    write_prompts(studio)
    providers.edited = edited_still(studio)
    take = generate_still(studio.root, "grin", "qwen-image", log=quiet)
    method, path, headers, body = providers.requests[0]
    assert (method, path) == ("POST", IMAGE_PATHS[0]) and headers["authorization"] == "Bearer wan-secret"
    image, text = body["input"]["messages"][0]["content"]
    assert text == {"text": take["prompt"]["text"]} and take["prompt"]["text"].startswith("character: Demo")
    assert body["model"] == "qwen-image-edit-plus"
    assert body["parameters"] == {"n": 1, "watermark": False, "prompt_extend": False, "negative_prompt": "still.negative text"}
    directory = take_dir(studio.root, "pose", "grin", take["id"])
    sent = (directory / "input.png").read_bytes()
    assert base64.b64decode(image["image"].split(",", 1)[1]) == sent and providers.requests[1][:2] == ("GET", "/edit.png")
    assert {p.name for p in directory.iterdir()} == {"take.json", "input.png", "source.png", "still.png"}
    assert (take["state"], take["source"]["provider"], take["prompt"]["negativeSent"]) == ("ready", "qwen-image", True)
    assert take["inputs"]["base"] == {"pose": "idle", "still": load_take_id(studio, "idle"), "file": "input.png",
                                      "sha256": hashlib.sha256(sent).hexdigest()}
    assert take["normalization"]["method"] == "registration" and take["qa"]["status"] == "pass", take["qa"]
    assert "wan-secret" not in (directory / "take.json").read_text(encoding="utf-8")
    assert approve_still(studio.root, "grin", take["id"])["id"] == take["id"]


def load_take_id(studio, pose: str) -> str:
    from spriteforge.production.records import load_owner
    return load_owner(studio.root, "pose", pose)["acceptedTake"]


def test_seedream_matches_the_canvas_aspect_and_sends_no_negative(studio, providers):
    add_pose(studio.root, "grin", "wide grin")
    write_prompts(studio)
    providers.edited = edited_still(studio, ".jpg")
    take = generate_still(studio.root, "grin", "seedream", log=quiet)
    _, path, headers, body = providers.requests[0]
    assert path == IMAGE_PATHS[1] and headers["authorization"] == "Bearer ark-secret"
    assert set(body) == {"model", "prompt", "image", "response_format", "watermark", "sequential_image_generation", "size"}
    width, height = CANVAS
    assert body["size"] == f"{round(width * 2048 / height)}x2048" and body["image"].startswith("data:image/png;base64,")
    assert (body["model"], body["response_format"], body["watermark"]) == ("doubao-seedream-4-0-250828", "b64_json", False)
    assert (take["state"], take["media"]["source"], take["prompt"]["negativeSent"]) == ("ready", "source.jpg", False)
    assert take["qa"]["status"] == "pass", take["qa"]


def test_still_generation_fails_before_a_paid_request(studio, providers, monkeypatch):
    add_pose(studio.root, "grin", "wide grin")
    with pytest.raises(ValueError, match="placeholder"):
        generate_still(studio.root, "grin", "qwen-image")
    preview = generate_still(studio.root, "grin", "qwen-image", dry_run=True)
    assert preview["request"]["input"]["messages"][0]["content"][0]["image"].startswith("<input.png sha256=")
    with pytest.raises(ValueError, match="base pose"):
        generate_still(studio.root, "idle", "qwen-image")
    with pytest.raises(ValueError, match="Unknown image provider"):
        generate_still(studio.root, "grin", "wan")
    write_prompts(studio)
    monkeypatch.delenv("DASHSCOPE_API_KEY")
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        generate_still(studio.root, "grin", "qwen-image")
    tools = load_tools(studio.root)
    tools["alpha"] = None
    save_tools(studio.root, tools)
    with pytest.raises(ValueError, match="alpha"):
        generate_still(studio.root, "grin", "seedream")
    assert providers.requests == [] and list_takes(studio.root, "pose", "grin") == []
    with pytest.raises(ValueError, match="Unknown video provider"):
        set_clip(studio.root, "smile_in", provider="seedream")


def test_refused_image_edit_is_kept_as_a_failed_take(studio, providers):
    add_pose(studio.root, "grin", "wide grin")
    write_prompts(studio)
    providers.image_error = "content check"
    with pytest.raises(ValueError, match="content check"):
        generate_still(studio.root, "grin", "qwen-image", log=quiet)
    [take] = list_takes(studio.root, "pose", "grin")
    assert take["state"] == "failed" and "HTTP 400" in take["error"]
    assert (take_dir(studio.root, "pose", "grin", take["id"]) / "input.png").is_file()


def test_page_job_generates_a_pose_still(studio, providers):
    add_pose(studio.root, "grin", "wide grin")
    write_prompts(studio)
    providers.edited = edited_still(studio)
    api = ProductionApi(studio.root)
    job = api.post("jobs", {"action": "generate", "pose": "grin", "provider": "qwen-image"})["job"]
    assert (job["kind"], job["owner"]) == ("pose", "grin")
    deadline = time.monotonic() + 60
    while api.job_list()[0]["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.05)
    done = api.job_list()[0]
    assert done["status"] == "succeeded" and done["result"].endswith("QA pass"), done
    assert any(line.startswith("Sent the idle still to qwen-image") for line in done["log"])
    with pytest.raises(ValueError, match="only generate"):
        api.post("jobs", {"action": "render", "pose": "grin"})
    kinds = {name: p["kind"] for name, p in api.overview()["tools"]["providers"].items()}
    assert kinds == {"wan": "video", "seedance": "video", "wan-cli": "video", "qwen-image": "image", "seedream": "image", "gpt-image": "image"}


@pytest.fixture
def wan_cli(studio, monkeypatch, tmp_path):
    """The wan-cli provider pointed at a fake CLI; returns the fake's state folder."""
    state = tmp_path / "wan-state"
    state.mkdir()
    (state / "credits").write_text("1000")
    video = write_video(studio.tmp / "cli-result.mp4", provider_frames(still(studio, "idle"), still(studio, "smile"), 24))
    monkeypatch.setenv("FAKE_WAN_STATE", str(state))
    monkeypatch.setenv("FAKE_WAN_VIDEO", str(video))
    tools = load_tools(studio.root)
    tools["providers"]["wan-cli"].update(command=[sys.executable, str(PROCESSORS / "fake_wan_cli.py")], pollSeconds=0.01)
    save_tools(studio.root, tools)
    add_clip(studio.root, "smile_in", "idle", "smile")
    write_prompts(studio)
    set_clip(studio.root, "smile_in", provider="wan-cli", resolution="480P")
    return state


def cli_calls(state):
    return [json.loads(line) for line in (state / "calls.jsonl").read_text(encoding="utf-8").splitlines()]


def test_wan_cli_needs_its_own_login_before_a_take(studio, wan_cli):
    with pytest.raises(ValueError, match="wan-cli is not logged in"):
        generate_clip_take(studio.root, "smile_in", log=quiet)
    assert list_takes(studio.root, "clip", "smile_in") == []
    assert [c["args"][:2] for c in cli_calls(wan_cli)] == [["auth", "status"]]


def test_wan_cli_generates_from_account_credits(studio, wan_cli):
    (wan_cli / "logged_in").touch()
    take = generate_clip_take(studio.root, "smile_in", log=quiet)
    calls = cli_calls(wan_cli)
    submit = next(c["args"] for c in calls if c["args"][0] == "frame2video")
    assert submit[submit.index("--resolution") + 1] == "480P" and submit[submit.index("--duration") + 1] == "2"
    assert "--audio-output=false" in submit and "--last-frame" in submit and "--model" not in submit
    assert submit[-3:] == ["--output", "json", "--quiet"] and submit[submit.index("--prompt") + 1].startswith("character: Demo")
    assert all(c["env"] == {"WAN_SKIP_SKILL_INSTALL": "1", "WAN_LANG": "en"} for c in calls)
    assert {c["cwd"] for c in calls}.isdisjoint({str(studio.root)})
    assert (wan_cli / "first.png").read_bytes() == (take_dir(studio.root, "clip", "smile_in", take["id"]) / "first.png").read_bytes()
    assert (take["state"], take["source"]["taskId"], take["media"]["count"]) == ("ready", "wan-cli-1", 24)
    assert (take["source"]["balanceBefore"]["credits"], take["source"]["balanceAfter"]["credits"]) == (1000, 990)
    assert take["prompt"]["negativeSent"] is False and take["source"]["request"]["command"][2].startswith("<first.png sha256=")

    set_clip(studio.root, "smile_in", last_frame="none")
    preview = generate_clip_take(studio.root, "smile_in", dry_run=True)
    assert "--last-frame" not in preview["request"]["command"]
    set_clip(studio.root, "smile_in", seed=7)
    with pytest.raises(ValueError, match="no seed option"):
        generate_clip_take(studio.root, "smile_in", dry_run=True)


def test_wan_cli_readiness_reads_no_secret(studio, monkeypatch, tmp_path):
    monkeypatch.delenv("WAN_ACCESS_KEY", raising=False)
    monkeypatch.setenv("WAN_CONFIG_DIR", str(tmp_path / "wan-home"))
    status = overview(studio.root)["tools"]["providers"]["wan-cli"]
    assert (status["credential"], status["keySet"]) == ("login", False)
    (tmp_path / "wan-home").mkdir()
    (tmp_path / "wan-home" / "config.json").write_text("{}")
    assert overview(studio.root)["tools"]["providers"]["wan-cli"]["keySet"] is True

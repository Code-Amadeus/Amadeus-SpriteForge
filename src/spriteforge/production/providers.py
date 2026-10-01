"""Image-to-video and image-edit providers.

Each adapter sends one documented request shape with the rendered prompt and
explicit parameters. Provider errors are raised with the provider's own message;
there are no silent retries, parameter downgrades or single-frame fallbacks. API
keys come only from the environment variable named in production/tools.json.

Video (clip takes) are generated from the first and last frames, or from the first
frame alone when the clip asks for it (``generation.lastFrame`` none); both
providers document the first-frame-only request.

- ``wan``: Alibaba Cloud Model Studio, Wan 2.7 image-to-video (``first_frame`` and
  ``last_frame`` media, asynchronous task). Result URLs expire after 24 hours, so
  a finished take is downloaded immediately.
- ``seedance``: Volcengine Ark content generation tasks (first/last frame roles).
  It has no negative prompt; takes record that the negative text was not sent.
- ``wan-cli``: Wan's own command-line tool (``@wan-ai/cli``, ``wan frame2video``),
  billed to the wan.video account's credits instead of Model Studio pay-as-you-go.
  The CLI keeps its own login (``wan auth login``): SpriteForge never reads that
  AccessKey, and checks ``wan auth status`` before a take is recorded. The CLI
  uploads the input images and saves the result without the watermark. It has no
  negative prompt or seed; takes record the account balance before and after.

Image edit (pose stills; input is the flattened base still):

- ``qwen-image``: Model Studio Qwen image editing (synchronous multimodal generation,
  one image and one instruction); the result URL is fetched at once.
- ``seedream``: Volcengine Ark Seedream image generation with a reference image,
  returned as base64. It has no negative prompt.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .media import copy_durable, write_durable


class ProviderError(ValueError):
    pass


@dataclass(frozen=True)
class ImageJob:
    prompt: str
    negative: str
    image: bytes
    references: list[bytes] = field(default_factory=list)
    size: tuple[int, int] | None = None


@dataclass(frozen=True)
class VideoJob:
    prompt: str
    negative: str
    first: bytes
    last: bytes | None
    duration: int
    resolution: str
    seed: int | None = None


def data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def image_label(name: str, png: bytes) -> str:
    return f"<{name}.png sha256={hashlib.sha256(png).hexdigest()[:16]}>"


def png_size(png: bytes) -> tuple[int, int]:
    if len(png) < 24 or png[:8] != b"\x89PNG\r\n\x1a\n" or png[12:16] != b"IHDR":
        raise ProviderError("Provider input must be a PNG image")
    width, height = struct.unpack(">II", png[16:24])
    return width, height


class Adapter:
    name = ""
    negative_prompt = True
    submit_path = ""
    cost_type = "metered"

    def __init__(self, config: dict) -> None:
        self.base_url = str(config.get("baseUrl") or "").rstrip("/")
        self.model = str(config.get("model") or "")
        self.key_env = str(config.get("apiKeyEnv") or "")
        self.poll_seconds = float(config.get("pollSeconds", 5))
        self.timeout_seconds = float(config.get("timeoutSeconds", 1800))
        self.request_seconds = float(config.get("requestSeconds", 120))
        if not self.base_url.startswith(("https://", "http://127.0.0.1", "http://localhost")) or not self.model or not self.key_env:
            raise ProviderError(f"Provider '{self.name}' needs an https baseUrl, a model and apiKeyEnv in production/tools.json")

    def key(self) -> str:
        value = os.environ.get(self.key_env, "").strip()
        if not value:
            raise ProviderError(f"Set the {self.key_env} environment variable to use provider '{self.name}'")
        return value

    def call(self, method: str, path: str, payload: dict | None = None, headers: dict | None = None) -> dict:
        request = urllib.request.Request(self.base_url + path, method=method,
                                         data=None if payload is None else json.dumps(payload).encode(),
                                         headers={"Authorization": f"Bearer {self.key()}", "Content-Type": "application/json",
                                                  **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=self.request_seconds) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:600]
            raise ProviderError(f"{self.name} HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(f"{self.name} request failed: {exc}") from exc

    def payload(self, job: VideoJob, first: str, last: str | None) -> dict:
        raise NotImplementedError

    def preview(self, job: VideoJob) -> dict:
        """The request as it will be sent, with images replaced by their hashes."""
        return self.payload(job, image_label("first", job.first), None if job.last is None else image_label("last", job.last))

    def request(self, job: VideoJob) -> dict:
        return self.payload(job, data_url(job.first), None if job.last is None else data_url(job.last))

    def submit(self, job: VideoJob) -> str:
        raise NotImplementedError

    def poll(self, task_id: str) -> tuple[str, str | None, str]:
        """('pending' | 'succeeded' | 'failed', video URL, provider detail)."""
        raise NotImplementedError

    def fetch_result(self, task_id: str, url: str | None, target: Path) -> None:
        """Store a finished task's video at ``target``."""
        download(url, target)

    def balance(self) -> dict | None:
        """The account balance, where the provider reports one; recorded with each take."""
        return None

    credential = "env"

    @classmethod
    def ready(cls, config: dict) -> bool:
        return bool(os.environ.get(str(config.get("apiKeyEnv") or "")))


class Wan(Adapter):
    name = "wan"

    def payload(self, job: VideoJob, first: str, last: str | None) -> dict:
        parameters = {"resolution": job.resolution, "duration": job.duration, "prompt_extend": False, "watermark": False}
        if job.seed is not None:
            parameters["seed"] = job.seed
        media = [{"type": "first_frame", "url": first}] + ([{"type": "last_frame", "url": last}] if last else [])
        inputs = {"prompt": job.prompt, "media": media}
        if job.negative:
            inputs["negative_prompt"] = job.negative
        return {"model": self.model, "input": inputs, "parameters": parameters}

    def submit(self, job: VideoJob) -> str:
        result = self.call("POST", "/services/aigc/video-generation/video-synthesis", self.request(job),
                           {"X-DashScope-Async": "enable"})
        task_id = (result.get("output") or {}).get("task_id")
        if not task_id:
            raise ProviderError(f"wan returned no task id: {json.dumps(result)[:400]}")
        return str(task_id)

    def poll(self, task_id: str) -> tuple[str, str | None, str]:
        output = self.call("GET", "/tasks/" + urllib.parse.quote(task_id)).get("output") or {}
        status = str(output.get("task_status") or "").upper()
        if status == "SUCCEEDED" and output.get("video_url"):
            return "succeeded", output["video_url"], status
        if status in {"FAILED", "CANCELED", "UNKNOWN"}:
            return "failed", None, f"{status}: {output.get('code', '')} {output.get('message', '')}".strip()
        return "pending", None, status


class Seedance(Adapter):
    name = "seedance"
    negative_prompt = False

    def payload(self, job: VideoJob, first: str, last: str | None) -> dict:
        content = [{"type": "text", "text": job.prompt},
                   {"type": "image_url", "image_url": {"url": first}, "role": "first_frame"}]
        if last:
            content.append({"type": "image_url", "image_url": {"url": last}, "role": "last_frame"})
        return {"model": self.model, "content": content, "ratio": "adaptive", "duration": job.duration,
                "resolution": job.resolution.lower(), "watermark": False, "generate_audio": False}

    def submit(self, job: VideoJob) -> str:
        result = self.call("POST", "/contents/generations/tasks", self.request(job))
        if not result.get("id"):
            raise ProviderError(f"seedance returned no task id: {json.dumps(result)[:400]}")
        return str(result["id"])

    def poll(self, task_id: str) -> tuple[str, str | None, str]:
        result = self.call("GET", "/contents/generations/tasks/" + urllib.parse.quote(task_id))
        status = str(result.get("status") or "").lower()
        url = (result.get("content") or {}).get("video_url")
        if status == "succeeded" and url:
            return "succeeded", url, status
        if status in {"failed", "cancelled", "expired"}:
            return "failed", None, f"{status}: {(result.get('error') or {}).get('message', '')}".strip()
        return "pending", None, status


class WanCli:
    """``wan frame2video`` through Wan's own CLI; see the module notes."""
    name = "wan-cli"
    negative_prompt = False
    credential = "login"
    cost_type = "credits"
    VIDEO_SUFFIXES = {".mp4", ".mov", ".webm"}

    def __init__(self, config: dict) -> None:
        command = config.get("command") or ["wan"]
        if not isinstance(command, list) or not all(isinstance(part, str) and part for part in command):
            raise ProviderError("Provider 'wan-cli' needs a 'command' list in production/tools.json, such as [\"wan\"]")
        self.command = command
        self.model = str(config.get("model") or "wan3.0")
        self.audio = bool(config.get("audioOutput", False))
        self.site = config.get("site")
        self.poll_seconds = float(config.get("pollSeconds", 10))
        self.timeout_seconds = float(config.get("timeoutSeconds", 1800))
        self.request_seconds = float(config.get("requestSeconds", 300))

    @staticmethod
    def ready(config: dict) -> bool:
        """Whether the CLI looks logged in, without running it: its AccessKey variable or its user config."""
        home = Path(os.environ.get("WAN_CONFIG_DIR") or Path.home() / ".wan")
        return bool(os.environ.get("WAN_ACCESS_KEY")) or (home / "config.json").is_file()

    def run(self, args: list[str], timeout: float | None = None) -> dict:
        """One CLI call with JSON output. It runs in an empty folder so no stray .env is read, and with
        the CLI's agent-skill installation switched off. A JSON error is returned for the caller to judge."""
        env = {**os.environ, "WAN_SKIP_SKILL_INSTALL": "1", "WAN_LANG": "en", "NO_COLOR": "1"}
        site = ["--site", str(self.site)] if self.site else []
        with tempfile.TemporaryDirectory(prefix="spriteforge-wan-") as folder:
            try:
                result = subprocess.run([*self.command, *args, *site, "--output", "json", "--quiet"], cwd=folder, env=env,
                                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                                        timeout=timeout or self.request_seconds)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ProviderError(f"wan-cli could not run: {exc}") from exc
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            data = None
        if not isinstance(data, dict):
            detail = (result.stderr or result.stdout).strip()[-600:]
            raise ProviderError(f"wan-cli exited with code {result.returncode}: {detail}")
        return data

    def key(self) -> None:
        status = self.run(["auth", "status"], 60)
        if status.get("ok") is False:
            raise ProviderError(f"wan-cli is not logged in ({status.get('errorMsg') or 'no account'}); run `wan auth login`")

    def balance(self) -> dict | None:
        try:
            return self.run(["credits"], 60)
        except ProviderError as exc:
            return {"ok": False, "errorMsg": str(exc)}

    def argv(self, job: VideoJob, first: str, last: str | None) -> list[str]:
        if job.seed is not None:
            raise ProviderError("wan-cli has no seed option; clear the clip's seed")
        args = ["frame2video", "--first-frame", first, *(["--last-frame", last] if last is not None else []),
                "--prompt", job.prompt, "--duration", str(job.duration), "--resolution", job.resolution.upper(),
                f"--audio-output={'true' if self.audio else 'false'}"]
        return args if self.model == "wan3.0" else [*args, "--model", self.model]

    def preview(self, job: VideoJob) -> dict:
        return {"command": self.argv(job, image_label("first", job.first),
                                     None if job.last is None else image_label("last", job.last))}

    def submit(self, job: VideoJob) -> str:
        with tempfile.TemporaryDirectory(prefix="spriteforge-wan-inputs-") as folder:
            first = Path(folder) / "first.png"
            first.write_bytes(job.first)
            last = None
            if job.last is not None:
                last = Path(folder) / "last.png"
                last.write_bytes(job.last)
            data = self.run(self.argv(job, str(first), None if last is None else str(last)))  # uploads the images
        if not data.get("taskId"):
            raise ProviderError(f"wan-cli returned no task id: {json.dumps(data, ensure_ascii=False)[:400]}")
        return str(data["taskId"])

    def poll(self, task_id: str) -> tuple[str, str | None, str]:
        data = self.run(["result", "get", task_id], 120)
        label = data.get("statusLabel")
        if not label:
            raise ProviderError(f"wan-cli could not read task {task_id}: {data.get('errorMsg') or json.dumps(data)[:300]}")
        if label == "succeeded":
            return "succeeded", None, label
        if label == "failed":
            return "failed", None, f"failed: {data.get('errorMsg') or data.get('statusDescription') or ''}".strip()
        return "pending", None, str(label)

    def fetch_result(self, task_id: str, url: str | None, target: Path) -> None:
        with tempfile.TemporaryDirectory(prefix="spriteforge-wan-result-") as folder:
            data = self.run(["result", "get", task_id, "--save", "--save-dir", folder], self.request_seconds)
            saved = [item for item in data.get("savedFiles") or [] if isinstance(item, dict) and item.get("path")]
            videos = [item for item in saved if Path(item["path"]).suffix.lower() in self.VIDEO_SUFFIXES]
            if len(videos) != 1:
                raise ProviderError(f"wan-cli saved {[Path(i['path']).name for i in saved]} for task {task_id}, not one video")
            if videos[0].get("watermark") == "with":
                raise ProviderError(f"wan-cli saved the watermarked video of task {task_id}")
            copy_durable(Path(videos[0]["path"]), target)


def image_dimensions(size: tuple[int, int], *, minimum_pixels: int = 0, maximum_pixels: int | None = None,
                     minimum_edge: int = 1, maximum_edge: int | None = None, ratio: float | None = None,
                     multiple: int = 1) -> tuple[int, int]:
    """Raise a requested size to the provider's legal minimum, preserving its aspect ratio.

    Maximums fail before submission. A smaller output would silently change the user's
    sheet/cell request; actual provider output is recorded separately, never resized here.
    """
    if not isinstance(size, (tuple, list)) or len(size) != 2 or any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in size):
        raise ProviderError("Image size needs two positive integer dimensions")
    width, height = size
    if ratio and max(width, height) / min(width, height) > ratio:
        raise ProviderError(f"Image aspect ratio must be no greater than {ratio:g}:1")
    scale = max(1, minimum_edge / min(width, height), math.sqrt(minimum_pixels / (width * height)))
    width, height = (math.ceil(v * scale / multiple) * multiple for v in (width, height))
    if maximum_edge and max(width, height) > maximum_edge or maximum_pixels and width * height > maximum_pixels:
        raise ProviderError("Requested image dimensions exceed this provider's supported size")
    return width, height


class ImageAdapter(Adapter):
    size_separator = "x"
    match_long_side = 2048
    supports_reference = False
    minimum_pixels = 0
    maximum_pixels = None
    minimum_edge = 1
    maximum_edge = None
    maximum_ratio = None

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.size = str(config["size"]) if config.get("size") else None

    def output_size(self, image: bytes, requested: tuple[int, int] | None = None) -> str | None:
        """None leaves the size to the provider; 'match' keeps the input's aspect ratio at a 2048 px long side."""
        if requested is not None:
            width, height = image_dimensions(requested, minimum_pixels=self.minimum_pixels, maximum_pixels=self.maximum_pixels,
                                            minimum_edge=self.minimum_edge, maximum_edge=self.maximum_edge, ratio=self.maximum_ratio)
            return f"{width}{self.size_separator}{height}"
        if self.size != "match":
            return self.size
        width, height = png_size(image)
        scale = self.match_long_side / max(width, height)
        return f"{round(width * scale)}{self.size_separator}{round(height * scale)}"

    def payload(self, job: ImageJob, image: str, references: list[str] | None = None) -> dict:
        raise NotImplementedError

    def preview(self, job: ImageJob) -> dict:
        return self.payload(job, image_label("input", job.image), [image_label(f"reference-{index + 1}", image) for index, image in enumerate(job.references)])

    def request(self, job: ImageJob) -> dict:
        return self.payload(job, data_url(job.image), [data_url(image) for image in job.references])

    def edit(self, job: ImageJob) -> bytes:
        """The edited image, fetched or decoded before returning."""
        raise NotImplementedError


class QwenImage(ImageAdapter):
    name = "qwen-image"
    size_separator = "*"
    supports_reference = True
    minimum_edge = 512
    maximum_edge = 2048

    def payload(self, job: ImageJob, image: str, references: list[str] | None = None) -> dict:
        images = [image, *(references or [])]
        if len(images) > 3:
            raise ProviderError("qwen-image-edit-plus supports at most three input images")
        parameters: dict = {"n": 1, "watermark": False, "prompt_extend": False}
        if job.negative:
            parameters["negative_prompt"] = job.negative
        size = self.output_size(job.image, job.size)
        if size:
            parameters["size"] = size
        return {"model": self.model, "parameters": parameters,
                "input": {"messages": [{"role": "user", "content": [*({"image": value} for value in images), {"text": job.prompt}]}]}}

    def edit(self, job: ImageJob) -> bytes:
        result = self.call("POST", "/services/aigc/multimodal-generation/generation", self.request(job))
        choices = (result.get("output") or {}).get("choices") or []
        images = [part["image"] for choice in choices for part in (choice.get("message") or {}).get("content") or []
                  if isinstance(part, dict) and part.get("image")]
        if not images:
            raise ProviderError(f"qwen-image returned no image: {result.get('code', '')} {result.get('message', '')}".strip())
        return fetch(images[0], self.request_seconds)


class Seedream(ImageAdapter):
    name = "seedream"
    negative_prompt = False
    supports_reference = True
    minimum_pixels = 921600
    maximum_pixels = 16777216
    maximum_ratio = 16

    def payload(self, job: ImageJob, image: str, references: list[str] | None = None) -> dict:
        payload = {"model": self.model, "prompt": job.prompt, "image": [image, *references] if references else image, "response_format": "b64_json",
                   "watermark": False, "sequential_image_generation": "disabled"}
        size = self.output_size(job.image, job.size)
        if size:
            payload["size"] = size
        return payload

    def edit(self, job: ImageJob) -> bytes:
        result = self.call("POST", "/images/generations", self.request(job))
        data = [item for item in result.get("data") or [] if isinstance(item, dict) and item.get("b64_json")]
        if not data:
            raise ProviderError(f"seedream returned no image: {json.dumps(result.get('error') or result)[:400]}")
        try:
            return base64.b64decode(data[0]["b64_json"], validate=True)
        except ValueError as exc:
            raise ProviderError("seedream returned invalid base64 image data") from exc


class GptImageCli:
    """One isolated Codex request, using its own login and a native thread-bound image.

    Availability is only an executable check, never a claim about authentication.
    Codex checks login/quota during the explicit request; failures retain the caller's
    existing failed-take lifecycle. No auth/config files or global image directory scans.
    """
    name = "gpt-image"
    credential = "command"
    cost_type = "planQuota"
    negative_prompt = False
    supports_reference = True

    def __init__(self, config: dict) -> None:
        command = config.get("command") or ["codex"]
        if not isinstance(command, list) or not command or not all(isinstance(value, str) and value for value in command):
            raise ProviderError("Provider 'gpt-image' needs a non-empty 'command' list in production/tools.json")
        self.command = command
        self.model = str(config.get("model") or "gpt-image-2")
        self.timeout_seconds = float(config.get("timeoutSeconds", 600))
        self.size = str(config.get("size") or "match")

    @staticmethod
    def ready(config: dict) -> bool:
        command = config.get("command") or ["codex"]
        return bool(isinstance(command, list) and command and isinstance(command[0], str) and
                    (shutil.which(command[0]) or Path(command[0]).is_file()))

    def key(self) -> None:
        if not self.ready({"command": self.command}):
            raise ProviderError("Configure the Codex CLI command for 'gpt-image'; its login is checked by Codex when requested")

    def output_size(self, image: bytes, requested: tuple[int, int] | None = None) -> str:
        if requested is None:
            if self.size == "match":
                requested = png_size(image)
            else:
                try:
                    requested = tuple(int(value) for value in self.size.split("x"))
                except ValueError as exc:
                    raise ProviderError("gpt-image size must be 'match' or WIDTHxHEIGHT") from exc
        width, height = image_dimensions(requested, minimum_pixels=655360, maximum_pixels=8294400,
                                        maximum_edge=3840, ratio=3, multiple=16)
        return f"{width}x{height}"

    def preview(self, job: ImageJob) -> dict:
        return {"model": self.model, "size": self.output_size(job.image, job.size), "prompt": job.prompt,
                "input": image_label("input", job.image),
                "references": [image_label(f"reference-{index + 1}", image) for index, image in enumerate(job.references)],
                "credential": self.credential, "costType": self.cost_type,
                "options": ["--ignore-user-config", "--ephemeral", "--skip-git-repo-check", "--json"]}

    def edit(self, job: ImageJob) -> bytes:
        self.key()
        size = self.output_size(job.image, job.size)
        # The configured process owns authentication. API-key environment overrides
        # are omitted so this plan-quota provider does not silently switch billing.
        env = dict(os.environ)
        for name in ("OPENAI_API_KEY", "CODEX_API_KEY"):
            env.pop(name, None)
        native_root = Path(env.get("CODEX_HOME") or Path.home() / ".codex") / "generated_images"
        schema = {"type": "object", "properties": {"image_path": {"type": ["string", "null"]}, "width": {"type": ["integer", "null"]},
                  "height": {"type": ["integer", "null"]}, "error": {"type": ["string", "null"]}},
                  "required": ["image_path", "width", "height", "error"], "additionalProperties": False}
        with tempfile.TemporaryDirectory(prefix="spriteforge-gpt-image-") as temporary:
            folder = Path(temporary)
            images = [folder / "input.png", *(folder / f"reference-{index + 1}.png" for index in range(len(job.references))) ]
            for target, content in zip(images, [job.image, *job.references]):
                png_size(content)
                write_durable(target, content)
            schema_file, result_file = folder / "schema.json", folder / "result.json"
            schema_file.write_text(json.dumps(schema), encoding="utf-8")
            prompt = (f"Invoke the built-in imagegen tool exactly once to edit the attached images with {self.model}. "
                      f"Request one PNG at {size}. Image 1 is the approved base; later images are references. "
                      "Do not retry. Do not use shell, exec, other image tools, or skills. "
                      "Do not read or write configuration, authentication, or credential files. "
                      "Keep the native generated image bytes untouched even if its dimensions differ. "
                      "Return its native generated_images path and actual width/height, without copying or moving it. "
                      "When no image exists, return null image_path/width/height and the error.\n\n"
                      + job.prompt)
            command = [*self.command, "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check", "--json",
                       "--sandbox", "workspace-write", "--cd", str(folder), "--output-schema", str(schema_file),
                       "--output-last-message", str(result_file), *[value for image in images for value in ("--image", str(image))], "-"]
            try:
                result = subprocess.run(command, cwd=folder, env=env, input=prompt, capture_output=True, text=True,
                                        encoding="utf-8", errors="replace", timeout=self.timeout_seconds)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ProviderError(f"gpt-image CLI could not run: {exc}") from exc
            if result.returncode:
                detail = (result.stderr or result.stdout).strip()[-600:]
                raise ProviderError(f"gpt-image CLI exited with code {result.returncode}: {detail}")
            events = []
            for line in result.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("type") == "thread.started":
                    events.append(event.get("thread_id"))
            if len(events) != 1 or not isinstance(events[0], str):
                raise ProviderError("gpt-image CLI did not identify exactly one native thread")
            try:
                thread_id = str(uuid.UUID(events[0]))
                thread_root = native_root.resolve() / thread_id
                if thread_root.resolve(strict=True) != thread_root:
                    raise ProviderError("gpt-image native thread path escaped generated_images")
                answer = json.loads(result_file.read_text(encoding="utf-8"))
                raw_path = answer.get("image_path") if isinstance(answer, dict) else None
                if not isinstance(raw_path, str) or not raw_path:
                    raise ProviderError("gpt-image CLI returned no native image path")
                output = Path(raw_path)
                if not output.is_absolute():
                    output = thread_root / output
                output = output.resolve(strict=True)
                if not output.is_relative_to(thread_root) or not output.is_file():
                    raise ProviderError("gpt-image output must belong to this invocation's native thread")
                content = output.read_bytes()
                png_size(content)
                from .media import read_bgra
                decoded, _ = read_bgra(output)
                if decoded.shape[0] < 1 or decoded.shape[1] < 1:
                    raise ProviderError("gpt-image returned an empty image")
                return content
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                if isinstance(exc, ProviderError):
                    raise
                raise ProviderError(f"gpt-image CLI returned no valid thread-bound PNG: {exc}") from exc


PROVIDERS = {"wan": Wan, "seedance": Seedance, "wan-cli": WanCli}
IMAGE_PROVIDERS = {"qwen-image": QwenImage, "seedream": Seedream, "gpt-image": GptImageCli}


def get_provider(name: str, tools: dict) -> Adapter | WanCli:
    if name not in PROVIDERS:
        raise ProviderError(f"Unknown video provider '{name}'; available: {', '.join(PROVIDERS)} (or 'manual')")
    return PROVIDERS[name]((tools.get("providers") or {}).get(name) or {})


def provider_status(name: str, config: dict) -> dict:
    """How a provider authenticates ('env': an API key variable; 'login': the tool's own login) and
    whether that looks ready, without contacting the provider."""
    adapter = PROVIDERS.get(name) or IMAGE_PROVIDERS.get(name)
    return {"credential": adapter.credential, "keySet": adapter.ready(config),
            "supportsReference": bool(getattr(adapter, "supports_reference", False)), "costType": adapter.cost_type} if adapter else {
                "credential": None, "keySet": False, "supportsReference": False, "costType": None}


def get_image_provider(name: str, tools: dict) -> ImageAdapter | GptImageCli:
    if name not in IMAGE_PROVIDERS:
        raise ProviderError(f"Unknown image provider '{name}'; available: {', '.join(IMAGE_PROVIDERS)}")
    return IMAGE_PROVIDERS[name]((tools.get("providers") or {}).get(name) or {})


def fetch(url: str, timeout: float = 300) -> bytes:
    if not url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        raise ProviderError("Refusing to download a result from a non-https URL")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError(f"Result download failed: {exc}") from exc
    if not data:
        raise ProviderError("Result download was empty")
    return data


def download(url: str, target: Path, timeout: float = 300) -> None:
    write_durable(target, fetch(url, timeout))

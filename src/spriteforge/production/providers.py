"""Image-to-video and image-edit providers.

Each adapter sends one documented request shape with the rendered prompt and
explicit parameters. Provider errors are raised with the provider's own message;
there are no silent retries, parameter downgrades or single-frame fallbacks. API
keys come only from the environment variable named in production/tools.json.

Video (clip takes):

- ``wan``: Alibaba Cloud Model Studio, Wan 2.7 image-to-video (``first_frame`` and
  ``last_frame`` media, asynchronous task). Result URLs expire after 24 hours, so
  a finished take is downloaded immediately.
- ``seedance``: Volcengine Ark content generation tasks (first/last frame roles).
  It has no negative prompt; takes record that the negative text was not sent.

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
import os
import struct
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .media import write_durable


class ProviderError(ValueError):
    pass


@dataclass(frozen=True)
class ImageJob:
    prompt: str
    negative: str
    image: bytes


@dataclass(frozen=True)
class VideoJob:
    prompt: str
    negative: str
    first: bytes
    last: bytes
    duration: int
    resolution: str
    seed: int | None = None


def data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def image_label(name: str, png: bytes) -> str:
    return f"<{name}.png sha256={hashlib.sha256(png).hexdigest()[:16]}>"


def png_size(png: bytes) -> tuple[int, int]:
    if png[:8] != b"\x89PNG\r\n\x1a\n" or png[12:16] != b"IHDR":
        raise ProviderError("Provider input must be a PNG image")
    width, height = struct.unpack(">II", png[16:24])
    return width, height


class Adapter:
    name = ""
    negative_prompt = True
    submit_path = ""

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

    def payload(self, job: VideoJob, first: str, last: str) -> dict:
        raise NotImplementedError

    def preview(self, job: VideoJob) -> dict:
        """The request as it will be sent, with images replaced by their hashes."""
        return self.payload(job, image_label("first", job.first), image_label("last", job.last))

    def submit(self, job: VideoJob) -> str:
        raise NotImplementedError

    def poll(self, task_id: str) -> tuple[str, str | None, str]:
        """('pending' | 'succeeded' | 'failed', video URL, provider detail)."""
        raise NotImplementedError


class Wan(Adapter):
    name = "wan"

    def payload(self, job: VideoJob, first: str, last: str) -> dict:
        parameters = {"resolution": job.resolution, "duration": job.duration, "prompt_extend": False, "watermark": False}
        if job.seed is not None:
            parameters["seed"] = job.seed
        inputs = {"prompt": job.prompt, "media": [{"type": "first_frame", "url": first}, {"type": "last_frame", "url": last}]}
        if job.negative:
            inputs["negative_prompt"] = job.negative
        return {"model": self.model, "input": inputs, "parameters": parameters}

    def submit(self, job: VideoJob) -> str:
        result = self.call("POST", "/services/aigc/video-generation/video-synthesis",
                           self.payload(job, data_url(job.first), data_url(job.last)), {"X-DashScope-Async": "enable"})
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

    def payload(self, job: VideoJob, first: str, last: str) -> dict:
        return {"model": self.model, "content": [
                    {"type": "text", "text": job.prompt},
                    {"type": "image_url", "image_url": {"url": first}, "role": "first_frame"},
                    {"type": "image_url", "image_url": {"url": last}, "role": "last_frame"}],
                "ratio": "adaptive", "duration": job.duration, "resolution": job.resolution.lower(),
                "watermark": False, "generate_audio": False}

    def submit(self, job: VideoJob) -> str:
        result = self.call("POST", "/contents/generations/tasks", self.payload(job, data_url(job.first), data_url(job.last)))
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


class ImageAdapter(Adapter):
    size_separator = "x"
    match_long_side = 2048

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.size = str(config["size"]) if config.get("size") else None

    def output_size(self, image: bytes) -> str | None:
        """None leaves the size to the provider; 'match' keeps the input's aspect ratio at a 2048 px long side."""
        if self.size != "match":
            return self.size
        width, height = png_size(image)
        scale = self.match_long_side / max(width, height)
        return f"{round(width * scale)}{self.size_separator}{round(height * scale)}"

    def payload(self, job: ImageJob, image: str) -> dict:
        raise NotImplementedError

    def preview(self, job: ImageJob) -> dict:
        return self.payload(job, image_label("input", job.image))

    def edit(self, job: ImageJob) -> bytes:
        """The edited image, fetched or decoded before returning."""
        raise NotImplementedError


class QwenImage(ImageAdapter):
    name = "qwen-image"
    size_separator = "*"

    def payload(self, job: ImageJob, image: str) -> dict:
        parameters: dict = {"n": 1, "watermark": False, "prompt_extend": False}
        if job.negative:
            parameters["negative_prompt"] = job.negative
        size = self.output_size(job.image)
        if size:
            parameters["size"] = size
        return {"model": self.model, "parameters": parameters,
                "input": {"messages": [{"role": "user", "content": [{"image": image}, {"text": job.prompt}]}]}}

    def edit(self, job: ImageJob) -> bytes:
        result = self.call("POST", "/services/aigc/multimodal-generation/generation", self.payload(job, data_url(job.image)))
        choices = (result.get("output") or {}).get("choices") or []
        images = [part["image"] for choice in choices for part in (choice.get("message") or {}).get("content") or []
                  if isinstance(part, dict) and part.get("image")]
        if not images:
            raise ProviderError(f"qwen-image returned no image: {result.get('code', '')} {result.get('message', '')}".strip())
        return fetch(images[0], self.request_seconds)


class Seedream(ImageAdapter):
    name = "seedream"
    negative_prompt = False

    def payload(self, job: ImageJob, image: str) -> dict:
        payload = {"model": self.model, "prompt": job.prompt, "image": image, "response_format": "b64_json",
                   "watermark": False, "sequential_image_generation": "disabled"}
        size = self.output_size(job.image)
        if size:
            payload["size"] = size
        return payload

    def edit(self, job: ImageJob) -> bytes:
        result = self.call("POST", "/images/generations", self.payload(job, data_url(job.image)))
        data = [item for item in result.get("data") or [] if isinstance(item, dict) and item.get("b64_json")]
        if not data:
            raise ProviderError(f"seedream returned no image: {json.dumps(result.get('error') or result)[:400]}")
        try:
            return base64.b64decode(data[0]["b64_json"], validate=True)
        except ValueError as exc:
            raise ProviderError("seedream returned invalid base64 image data") from exc


PROVIDERS = {"wan": Wan, "seedance": Seedance}
IMAGE_PROVIDERS = {"qwen-image": QwenImage, "seedream": Seedream}


def get_provider(name: str, tools: dict) -> Adapter:
    if name not in PROVIDERS:
        raise ProviderError(f"Unknown video provider '{name}'; available: {', '.join(PROVIDERS)} (or 'manual')")
    return PROVIDERS[name]((tools.get("providers") or {}).get(name) or {})


def get_image_provider(name: str, tools: dict) -> ImageAdapter:
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

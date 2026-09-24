"""Image-to-video providers.

Each adapter sends one documented request shape: an opaque first frame, a last
frame, the rendered prompt and explicit parameters. Provider errors are raised
with the provider's own message; there are no silent retries, parameter
downgrades or single-frame fallbacks. API keys come only from the environment
variable named in production/tools.json.

- ``wan``: Alibaba Cloud Model Studio, Wan 2.7 image-to-video (``first_frame`` and
  ``last_frame`` media, asynchronous task). Result URLs expire after 24 hours, so
  a finished take is downloaded immediately.
- ``seedance``: Volcengine Ark content generation tasks (first/last frame roles).
  It has no negative prompt; takes record that the negative text was not sent.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .media import write_durable


class ProviderError(ValueError):
    pass


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
            with urllib.request.urlopen(request, timeout=120) as response:
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


PROVIDERS = {"wan": Wan, "seedance": Seedance}


def get_provider(name: str, tools: dict) -> Adapter:
    if name not in PROVIDERS:
        raise ProviderError(f"Unknown provider '{name}'; available: {', '.join(PROVIDERS)} (or 'manual')")
    return PROVIDERS[name]((tools.get("providers") or {}).get(name) or {})


def download(url: str, target: Path, timeout: float = 300) -> None:
    if not url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        raise ProviderError("Refusing to download a result from a non-https URL")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError(f"Result download failed: {exc}") from exc
    if not data:
        raise ProviderError("Result download was empty")
    write_durable(target, data)

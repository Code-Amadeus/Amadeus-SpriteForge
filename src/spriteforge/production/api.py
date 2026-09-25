"""HTTP operations behind the production page of the local editor.

Reads return the production overview and take media. Writes are decisions,
prompt versions, clip settings, uploads and background jobs (still generation;
clip generation, resume and render). Only one job may run for a pose or clip at
a time; paid generation is requested only by an explicit user action in the page.
"""
from __future__ import annotations

import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..workspace import resolve_asset
from .records import decide, production_dir

MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime"}
UPLOAD_LIMIT = 2 * 1024 ** 3


class ProductionApi:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()

    def available(self) -> bool:
        return (production_dir(self.workspace) / "character.json").is_file()

    def overview(self) -> dict:
        from .project import overview
        if not self.available():
            return {"ok": True, "initialized": False}
        return {"ok": True, "initialized": True, **overview(self.workspace)}

    def media(self, raw: str) -> tuple[Path, str]:
        path = resolve_asset(self.workspace, raw)
        if not path.is_relative_to(production_dir(self.workspace)) or path.suffix.lower() not in MEDIA_TYPES \
                or not path.is_file() or any(part.startswith(".") for part in path.relative_to(self.workspace).parts):
            raise ValueError("Not a production media file")
        return path, MEDIA_TYPES[path.suffix.lower()]

    def post(self, route: str, body: dict) -> dict:
        from . import project, prompts
        if route == "decision":
            kind, owner, take, action = body.get("kind"), body.get("owner"), body.get("take"), body.get("action")
            if kind == "pose" and action == "accept":
                from .stills import approve_still
                return {"take": approve_still(self.workspace, owner, take, body.get("reason", ""))}
            return {"take": decide(self.workspace, kind, owner, take, action, body.get("reason", ""))}
        if route == "prompt":
            with self.lock:
                library = prompts.load_library(self.workspace)
                version = prompts.set_block(library, str(body.get("block")), body.get("text"), body.get("description"))
                prompts.save_library(self.workspace, library)
            return {"block": body.get("block"), "version": version}
        if route == "clip-settings":
            raw = body.get("changes") or {}
            changes = {k: v for k, v in raw.items() if k in project.CLIP_SETTINGS}
            return {"clip": project.set_clip(self.workspace, str(body.get("clip")), mouth=raw.get("mouth"),
                                             mouth_source=raw.get("mouth_source"), **changes)}
        if route == "closed-mouth":
            pose = body.get("pose")
            return {"owner": project.set_closed_mouth(self.workspace, body.get("source") or None,
                                                      pose_id=str(pose) if pose else None)}
        if route == "pose":
            return {"pose": project.add_pose(self.workspace, str(body.get("id")), str(body.get("description") or ""))}
        if route == "clip":
            return {"clip": project.add_clip(self.workspace, str(body.get("id")), str(body.get("from")),
                                             str(body.get("to")), body.get("phase") or None)}
        if route == "graph-sync":
            return project.graph_sync(self.workspace, add_missing=bool(body.get("addMissing")))
        if route == "jobs":
            kind = "pose" if body.get("pose") else "clip"
            return {"job": self.start(str(body.get("action")), kind, str(body.get(kind)), body.get("provider"), body.get("take"))}
        raise KeyError(route)

    def start(self, action: str, kind: str, owner: str, provider: str | None = None, take_id: str | None = None) -> dict:
        from .records import load_owner
        load_owner(self.workspace, kind, owner)
        if kind == "pose":
            if action != "generate":
                raise ValueError("A pose job can only generate a still")
            from .stills import generate_still

            def work(log):
                take = generate_still(self.workspace, owner, str(provider or ""), log=log)
                return f"{take['id']} QA {take['qa']['status']}"
        elif action == "render":
            from .render import render_clip

            def work(log):
                return render_clip(self.workspace, owner, log=log)["qa"]["status"]
        elif action == "generate":
            from .clips import generate_clip_take

            def work(log):
                return generate_clip_take(self.workspace, owner, provider=provider or None, log=log)["id"]
        elif action == "resume":
            from .clips import resume_clip_take

            def work(log):
                return resume_clip_take(self.workspace, owner, str(take_id), log=log)["state"]
        else:
            raise ValueError("Job action must be render, generate or resume")
        with self.lock:
            if any((j["kind"], j["owner"]) == (kind, owner) and j["status"] == "running" for j in self.jobs.values()):
                raise ValueError(f"A job for {kind} {owner} is already running")
            job = {"id": uuid.uuid4().hex[:12], "action": action, "kind": kind, "owner": owner, "status": "running", "log": [],
                   "startedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "result": None, "error": None}
            self.jobs[job["id"]] = job

        def run() -> None:
            def log(message: object) -> None:
                with self.lock:
                    job["log"] = [*job["log"], str(message)][-300:]
            try:
                result = work(log)
                with self.lock:
                    job.update(status="succeeded", result=result)
            except Exception as exc:  # the job reports every failure to the page
                with self.lock:
                    job.update(status="failed", error=str(exc))
        threading.Thread(target=run, daemon=True, name=f"spriteforge-{action}-{kind}-{owner}").start()
        return dict(job)

    def job_list(self) -> list[dict]:
        with self.lock:
            return sorted((dict(j) for j in self.jobs.values()), key=lambda j: j["startedAt"], reverse=True)

    def upload(self, kind: str, owner: str, name: str, stream, length: int, fps: float | None, note: str) -> dict:
        if not 0 < length <= UPLOAD_LIMIT:
            raise ValueError("Upload size is missing or too large")
        suffix = Path(name).suffix.lower()
        if suffix not in MEDIA_TYPES:
            raise ValueError(f"Unsupported upload type {suffix or '(none)'}")
        staging = production_dir(self.workspace) / ".uploads"
        staging.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=staging) as temporary:
            target = Path(temporary) / f"upload{suffix}"
            remaining = length
            with open(target, "wb") as handle:
                while remaining:
                    chunk = stream.read(min(remaining, 1 << 20))
                    if not chunk:
                        raise ValueError("Upload ended early")
                    handle.write(chunk)
                    remaining -= len(chunk)
            if kind == "pose":
                from .stills import import_still
                return {"take": import_still(self.workspace, owner, target, note=note or f"uploaded {name}")}
            if kind == "clip":
                from .clips import import_clip_take
                return {"take": import_clip_take(self.workspace, owner, target, fps=fps, note=note or f"uploaded {name}")}
        raise ValueError("Uploads belong to a pose or a clip")

"""HTTP operations behind the production page of the local editor.

Reads return the production overview and take media. Writes are decisions,
prompt versions, clip settings, uploads and background jobs (still generation or
adoption of a clip frame; clip generation, resume and render). Only one job may run
for a pose or clip at a time; paid generation is requested only by an explicit user
action in the page. Export and publishing clip outputs share this server's job
lock. Separate CLI processes are outside this local scheduling boundary.
"""
from __future__ import annotations

import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..workspace import png_frames, resolve_asset
from .records import decide, production_dir, set_take_note

MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
               ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime"}
UPLOAD_LIMIT = 2 * 1024 ** 3


class ProductionApi:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.provider_locks: dict[str, threading.Lock] = {}
        self.workflows = None

    def available(self) -> bool:
        return (production_dir(self.workspace) / "character.json").is_file()

    def overview(self) -> dict:
        from .project import overview
        if not self.available():
            return {"ok": True, "initialized": False}
        return {"ok": True, "initialized": True, **overview(self.workspace)}

    def clip_input(self, clip_id: str, end: str) -> bytes:
        """The first or last frame image exactly as a provider receives it (what 'prepare' writes)."""
        from .clips import clip_inputs
        from .records import load_character, load_owner
        if end not in {"first", "last"}:
            raise ValueError("An input is the clip's first or last frame")
        first, last, _ = clip_inputs(self.workspace, load_character(self.workspace), load_owner(self.workspace, "clip", clip_id))
        if end == "last" and last is None:
            raise ValueError(f"Clip {clip_id} is generated from its first frame only")
        return first if end == "first" else last

    def pose_input(self, pose_id: str) -> bytes:
        """The approved base image used by prepare and still generation, without a write."""
        from .records import load_character, load_owner
        from .stills import still_input
        load_owner(self.workspace, "pose", pose_id)
        return still_input(self.workspace, load_character(self.workspace))[0]

    def media(self, raw: str) -> tuple[Path, str]:
        path = resolve_asset(self.workspace, raw)
        if not path.is_relative_to(production_dir(self.workspace)) or path.suffix.lower() not in MEDIA_TYPES \
                or not path.is_file() or any(part.startswith(".") for part in path.relative_to(self.workspace).parts):
            raise ValueError("Not a production media file")
        return path, MEDIA_TYPES[path.suffix.lower()]

    def post(self, route: str, body: dict) -> dict:
        from . import project, prompts
        if route == "workflows" or route.startswith("workflows/"):
            from .workflows import save_workflow, template_workflow
            engine = self.workflow_engine()
            if route in {"workflows", "workflows/import"}:
                with self.lock:
                    return {"workflow": save_workflow(self.workspace, body, imported=route.endswith("/import"))}
            if route == "workflows/template":
                return {"workflow": template_workflow(self.workspace, body.get("template"), pose=body.get("pose"),
                                                       clip=body.get("clip"), concept=body.get("concept"), identifier=body.get("id"))}
            if route == "workflows/plan":
                return engine.plan(body.get("id"), rerun=body.get("rerun"))
            if route == "workflows/run":
                plan = engine.confirmed_plan(body.get("id"), body.get("planHash"), body.get("confirmPaid"),
                                             confirm_imported=body.get("confirmImported", False), rerun=body.get("rerun"))
                run_id = uuid.uuid4().hex
                with self.lock:
                    image_locks = {entry["provider"]: self.provider_locks.setdefault(entry["provider"], threading.Lock())
                                   for entry in plan["entries"].values() if entry["kind"] in {"image-edit", "concept-sheet"}
                                   and not entry["cacheHit"]}

                def workflow(log):
                    result = engine.run(body["id"], plan_hash=body["planHash"], confirm_paid=body["confirmPaid"],
                                        confirm_imported=body.get("confirmImported", False), rerun=body.get("rerun"), run_id=run_id,
                                        provider_locks=image_locks, log=log)
                    return result["id"]

                return {"job": self._launch("workflow", "workflow", body["id"], workflow,
                                             details={"workflow": body["id"], "runId": run_id, "owners": plan["owners"]})}
            raise KeyError(route)
        if route == "tools-settings":
            from .tools import set_ui_defaults
            with self.lock:
                return {"defaults": set_ui_defaults(self.workspace, body.get("defaults"))}
        if route == "review-known":
            from .issues import set_known
            return set_known(self.workspace, body.get("key"), body.get("note", ""), clear=body.get("clear", False))
        if route == "behavior/trigger-test":
            return self.behavior_trigger_test(body.get("minutes", 10), body.get("seed", 1), body.get("events", []))
        if route == "export":
            from .exports import export_workspace, validate_version
            version = validate_version(body.get("version"))

            def export(log):
                return export_workspace(self.workspace, version, notes=body.get("notes", ""), log=log)["version"]

            return {"job": self._launch("export", "export", version, export)}
        if route == "adopt-processed":
            from .render import adopt_processed_take
            with self.lock:
                if any(job["action"] == "export" and job["status"] == "running" for job in self.jobs.values()):
                    raise ValueError("An export is running; published clip output cannot change until it finishes")
                if any(("clip", body.get("clip")) in self.job_owners(job) and job["status"] == "running"
                       for job in self.jobs.values()):
                    raise ValueError(f"A job for clip {body.get('clip')} is already running; wait before adopting its output")
                return {"take": adopt_processed_take(self.workspace, body.get("clip"), body.get("take"))}
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
        if route == "pose-expect":
            from .stills import set_expected
            return {"pose": set_expected(self.workspace, body.get("pose"), body.get("headTopY"), body.get("headCenterX"))}
        if route == "clip":
            return {"clip": project.add_clip(self.workspace, str(body.get("id")), str(body.get("from")),
                                             str(body.get("to")), body.get("phase") or None)}
        if route == "variant":
            with self.lock:
                return {"clip": project.add_variant(self.workspace, body.get("from"), body.get("id"))}
        if route == "plan-clips":
            with self.lock:
                return {"clips": project.plan_clips(self.workspace, body.get("clips"))}
        if route == "concepts":
            return {"job": self.start_concept(body.get("poses"), body.get("grid", "3x2"), body.get("provider"))}
        if route == "concept-cell":
            from .concepts import set_cell
            with self.lock:
                if body.get("pose") is not None and any(job["kind"] == "concept" and job["owner"] == body.get("sheet")
                                                       and job["status"] == "running" for job in self.jobs.values()):
                    raise ValueError("Cannot reassign a cell while a job for its sheet is running")
                return {"sheet": set_cell(self.workspace, body.get("sheet"), body.get("cell"),
                                          picked=body.get("picked"), pose=body.get("pose"))}
        if route == "take-note":
            with self.lock:
                return {"take": set_take_note(self.workspace, body.get("kind"), body.get("owner"),
                                              body.get("take"), body.get("note"))}
        if route == "mouth-set":
            changes = body.get("changes")
            fields = {"cx", "cy", "width", "height", "curve"}
            if not isinstance(changes, dict) or set(changes) - fields:
                raise ValueError("Mouth set changes only accept cx, cy, width, height and curve")
            with self.lock:
                return {"mouthSet": project.set_mouth_set(self.workspace, body.get("name"), **changes)}
        if route == "import-frames":
            from .clips import import_clip_take
            path = resolve_asset(self.workspace, body.get("path"))
            if not path.is_dir():
                raise ValueError("Frame import needs a workspace folder")
            png_frames(self.workspace, path)  # validate every resolved PNG before copying any source
            return {"take": import_clip_take(self.workspace, body.get("clip"), path, fps=body.get("fps"),
                                              note=body.get("note", ""))}
        if route == "graph-sync":
            return project.graph_sync(self.workspace, add_missing=bool(body.get("addMissing")))
        if route == "canvas":
            with self.lock:
                return {"positions": project.save_canvas_layout(self.workspace, body.get("positions"))}
        if route == "jobs":
            if body.get("action") == "concept-reroll":
                return {"job": self.start_reroll(body.get("sheet"), body.get("cell"), body.get("provider"))}
            kind = "pose" if body.get("pose") else "clip"
            adopt = {"clip": str(body.get("clip")), "frame": body.get("frame") or "last"} if kind == "pose" else None
            return {"job": self.start(str(body.get("action")), kind, str(body.get(kind)), body.get("provider"),
                                      body.get("take"), adopt, based_on=body.get("basedOn"), note=body.get("note", ""),
                                      concept=body.get("concept"))}
        raise KeyError(route)

    def start(self, action: str, kind: str, owner: str, provider: str | None = None, take_id: str | None = None,
              adopt: dict | None = None, *, based_on: str | None = None, note: str = "", concept: dict | None = None) -> dict:
        """``adopt`` names the clip and frame whose take (``take_id``) a pose job takes its still from."""
        from .records import load_owner
        load_owner(self.workspace, kind, owner)
        if (based_on is not None or note != "") and (kind != "clip" or action != "generate"):
            raise ValueError("basedOn and note only apply to clip generation jobs")
        if concept is not None and (kind != "pose" or action != "generate"):
            raise ValueError("Concept references only apply to pose generation jobs")
        if kind == "pose" and action == "adopt" and adopt:
            from .stills import adopt_frame

            def work(log):
                take = adopt_frame(self.workspace, adopt["clip"], str(take_id), pose_id=owner, frame=adopt["frame"],
                                   log=log)
                return f"{take['id']} QA {take['qa']['status']}"
        elif kind == "pose":
            if action != "generate":
                raise ValueError("A pose job can only generate a still or adopt a clip frame")
            from .stills import generate_still
            from .tools import load_tools
            provider = provider or load_tools(self.workspace)["defaults"]["stillProvider"]
            if concept is not None:
                from .concepts import concept_reference
                if not isinstance(concept, dict) or set(concept) != {"sheet", "cell"}:
                    raise ValueError("Concept reference needs sheet and cell")
                concept_reference(self.workspace, concept["sheet"], concept["cell"], owner)

            def work(log):
                take = generate_still(self.workspace, owner, provider, concept=concept, log=log)
                return f"{take['id']} QA {take['qa']['status']}"
        elif action == "render-take":
            from .render import render_take

            def work(log):
                return render_take(self.workspace, owner, take_id, log=log)["qa"]["status"]
        elif action == "render":
            from .render import render_clip

            def work(log):
                return render_clip(self.workspace, owner, log=log)["qa"]["status"]
        elif action == "generate":
            from .clips import generate_clip_take, validate_generation_metadata
            validate_generation_metadata(self.workspace, owner, based_on, note)

            def work(log):
                return generate_clip_take(self.workspace, owner, provider=provider or None, based_on=based_on,
                                          note=note, log=log)["id"]
        elif action == "resume":
            from .clips import resume_clip_take

            def work(log):
                return resume_clip_take(self.workspace, owner, str(take_id), log=log)["state"]
        else:
            raise ValueError("Job action must be render, render-take, generate or resume")
        return self._launch(action, kind, owner, work, provider=provider if kind == "pose" and action == "generate" else None)

    def start_concept(self, poses: object, grid: object, provider: str | None) -> dict:
        from .concepts import generate_sheet, grid_spec
        from .records import new_take_id
        from .tools import load_tools
        grid = grid_spec(grid)
        provider = provider or load_tools(self.workspace)["defaults"]["conceptProvider"]
        sheet_id = new_take_id()

        def work(log):
            return generate_sheet(self.workspace, poses, grid, provider, sheet_id=sheet_id, log=log)["id"]

        return self._launch("concept", "concept", sheet_id, work, provider=provider, details={"poses": poses, "sheet": sheet_id})

    def start_reroll(self, sheet: str, cell: object, provider: str | None) -> dict:
        from .concepts import reroll_cell
        from .tools import load_tools
        provider = provider or load_tools(self.workspace)["defaults"]["conceptProvider"]

        def work(log):
            return reroll_cell(self.workspace, sheet, cell, provider, log=log)["id"]

        return self._launch("concept-reroll", "concept", sheet, work, provider=provider, details={"sheet": sheet, "cell": cell})

    def _launch(self, action: str, kind: str, owner: str, work, *, provider: str | None = None,
                details: dict | None = None) -> dict:
        if provider is not None and not isinstance(provider, str):
            raise ValueError("Provider must be a provider id")
        with self.lock:
            active = [job for job in self.jobs.values() if job["status"] == "running"]
            if action == "workflow" and any(job["action"] == "workflow" for job in active):
                raise ValueError("A workflow is already running")
            if action == "export" and any(job["action"] == "render" for job in active):
                raise ValueError("A published render is running; wait for it before exporting")
            if action == "render" and any(job["action"] == "export" for job in active):
                raise ValueError("An export is running; published clip output cannot change until it finishes")
            reservations = self.job_owners({"kind": kind, "owner": owner, **(details or {})})
            if any(self.job_owners(job) & reservations or (job["kind"], job["owner"]) == (kind, owner) for job in active):
                raise ValueError(f"A job for {kind} {owner} is already running")
            job = {"id": uuid.uuid4().hex[:12], "action": action, "kind": kind, "owner": owner, "status": "running", "log": [],
                   "startedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "result": None, "error": None,
                   **(details or {}), **({"provider": provider} if provider else {})}
            self.jobs[job["id"]] = job
            provider_lock = self.provider_locks.setdefault(provider, threading.Lock()) if provider else None

        def run() -> None:
            def log(message: object) -> None:
                with self.lock:
                    job["log"] = [*job["log"], str(message)][-300:]
            try:
                if provider_lock:
                    log(f"Queued for {provider}; this job sends one requested image call")
                    with provider_lock:
                        result = work(log)
                else:
                    result = work(log)
                with self.lock:
                    job.update(status="succeeded", result=result)
            except Exception as exc:  # the job reports every failure to the page
                with self.lock:
                    job.update(status="failed", error=str(exc))
        threading.Thread(target=run, daemon=True, name=f"spriteforge-{action}-{kind}-{owner}").start()
        return dict(job)

    @staticmethod
    def job_owners(job: dict) -> set[tuple[str, str]]:
        result = {(item["kind"], item["id"]) for item in job.get("owners", [])}
        if job["kind"] in {"pose", "clip"}:
            result.add((job["kind"], job["owner"]))
        return result

    def workflow_engine(self):
        from .workflows import WorkflowEngine
        with self.lock:
            if self.workflows is None:
                self.workflows = WorkflowEngine(self.workspace)
            return self.workflows

    def workflow_get(self, suffix: str) -> dict:
        from .workflows import TEMPLATES, list_workflows, load_workflow, read_run, schema
        if suffix in {"", "/"}:
            return {"workflows": list_workflows(self.workspace)}
        if suffix == "/schema":
            return schema(self.workspace)
        if suffix == "/templates":
            return {"templates": TEMPLATES}
        if suffix.startswith("/runs/"):
            run_id = suffix.removeprefix("/runs/")
            try:
                return {"run": read_run(self.workspace, run_id)}
            except FileNotFoundError:
                with self.lock:
                    if any(job.get("action") == "workflow" and job.get("runId") == run_id
                           and job.get("status") == "running" for job in self.jobs.values()):
                        return {"run": None}
                raise
        return {"workflow": load_workflow(self.workspace, suffix.removeprefix("/"))}

    def job_list(self) -> list[dict]:
        with self.lock:
            return sorted((dict(j) for j in self.jobs.values()), key=lambda j: j["startedAt"], reverse=True)

    def review_seam(self, key: str) -> dict:
        from .issues import seam_detail
        return seam_detail(self.workspace, key)

    def export_preflight(self) -> dict:
        from .exports import preflight
        return preflight(self.workspace)

    def export_diff(self) -> dict:
        from .exports import installed_diff
        return installed_diff(self.workspace)

    def _behavior_snapshot(self, minutes: object, seed: object) -> tuple:
        from ..graph import validate_graph
        from ..workspace import clip_frames, read_json
        from .project import overview
        from .records import bound_clip
        if isinstance(minutes, str):
            try:
                minutes = int(minutes)
            except ValueError:
                raise ValueError("Behavior minutes must be 10, 30 or 60") from None
        if isinstance(seed, str):
            try:
                seed = int(seed)
            except ValueError:
                raise ValueError("Seed must be an unsigned 32-bit integer") from None
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes not in {10, 30, 60}:
            raise ValueError("Behavior minutes must be 10, 30 or 60")
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xFFFFFFFF:
            raise ValueError("Seed must be an unsigned 32-bit integer")
        path = resolve_asset(self.workspace, "graph_config.json")
        graph = read_json(path) if path.is_file() else {"nodes": [], "edges": []}
        if graph["nodes"]:
            graph = validate_graph(self.workspace, graph, check_assets=False)
        data = overview(self.workspace, graph=graph)
        clips = {clip["id"]: clip for clip in data["clips"]}
        bindings = {node["id"]: bound_clip(node.get("root")) for node in graph["nodes"]}
        durations, nodes = {}, {}
        for node in graph["nodes"]:
            clip_id = bindings[node["id"]]
            count = ((clips.get(clip_id) or {}).get("render") or {}).get("frameCount")
            if clip_id is None:
                try:
                    count = len(clip_frames(self.workspace, node))
                except (ValueError, OSError):
                    count = None
            known = isinstance(count, int) and not isinstance(count, bool) and count > 0
            duration = count * node["frameIntervalMs"] / 1000 if known else 2.5
            durations[node["id"]] = duration
            nodes[node["id"]] = {"id": node["id"], "label": node["label"], "clip": clip_id,
                                 "durationS": duration, "durationKnown": known}
        return minutes, seed, graph, data, bindings, durations, nodes

    def behavior_stats(self, minutes: object = 10, seed: object = 1) -> dict:
        from ..behavior import pose_coverage, root_node, simulate, topology_summary
        minutes, seed, graph, data, bindings, durations, nodes = self._behavior_snapshot(minutes, seed)
        edge_issues = {issue["edge"]: issue for issue in data["issues"] if issue["kind"] == "edge" and issue["level"] == "fail"}
        simulation = simulate(graph, durations, seconds=minutes * 60, seed=seed, failing_edges=set(edge_issues))
        simulation["visitedSeamFailures"] = [edge_issues[edge]["key"] for edge in simulation.pop("jumps")]
        simulation.pop("route")
        simulation.pop("events")
        ship = {"blocking": [issue for issue in data["issues"] if issue["blocksExport"]]}
        out_of_date = {}
        clips = {clip["id"]: clip for clip in data["clips"]}
        for issue in ship["blocking"]:
            if issue["kind"] == "node" and ((clips.get(issue.get("clip")) or {}).get("render") or {}).get("state") in {"missing", "stale"}:
                out_of_date[issue["node"]] = nodes.get(issue["node"], {"id": issue["node"], "label": issue["clip"], "clip": issue["clip"]})
        ship["outOfDate"] = list(out_of_date.values())
        ship.update({key: [nodes[node] for node in ids] for key, ids in topology_summary(graph).items()})
        root = root_node(graph)
        root_clip = clips.get(bindings.get(root)) or {}
        root_pose = root_clip.get("to")
        groups = {}
        for node in graph["nodes"]:
            clip = clips.get(bindings[node["id"]])
            pose = (clip["from"] if clip["to"] == data["character"]["basePose"] and clip["kind"] == "transition"
                    else clip["to"]) if clip else None
            label = pose or node["label"]
            group_key = (pose, label)
            group = groups.setdefault(group_key, {"pose": pose, "label": label + " family" if
                                                 (pose is not None and pose == root_pose) or (pose is None and root and node["label"] == nodes[root]["label"])
                                                 else label, "seconds": 0, "share": 0, "nodes": []})
            time = simulation["nodeTime"][node["id"]]
            group["seconds"] += time
            group["nodes"].append({**nodes[node["id"]], "seconds": time,
                                   "share": time / simulation["seconds"] if simulation["seconds"] else 0,
                                   "visits": simulation["nodeVisits"][node["id"]]})
        for group in groups.values():
            group["seconds"] = round(group["seconds"], 6)
            group["share"] = group["seconds"] / simulation["seconds"] if simulation["seconds"] else 0
            group["nodes"].sort(key=lambda node: (-node["seconds"], node["id"]))
        return {"available": bool(graph["nodes"]), "minutes": minutes, "seed": seed, "root": root, "ship": ship,
                "simulation": simulation, "groups": sorted(groups.values(), key=lambda group: (-group["seconds"], group["label"])),
                "coverage": pose_coverage(data["poses"], data["clips"], bindings, data["character"]["basePose"])}

    def behavior_trigger_test(self, minutes: object = 10, seed: object = 1, events: object = None) -> dict:
        from ..behavior import root_node, simulate
        minutes, seed, graph, data, bindings, durations, _ = self._behavior_snapshot(minutes, seed)
        if not isinstance(events, list):
            raise ValueError("Trigger events must be a list")
        clips = {clip["id"]: clip for clip in data["clips"]}
        speech = {node for node, clip_id in bindings.items() if (clips.get(clip_id) or {}).get("mouth")}
        failing = {issue["edge"] for issue in data["issues"] if issue["kind"] == "edge" and issue["level"] == "fail"}
        result = simulate(graph, durations, seconds=minutes * 60, seed=seed, events=events, speech_targets=speech,
                          failing_edges=failing, trace=True)
        return {"minutes": minutes, "seed": seed, "root": root_node(graph), "route": result["route"],
                "events": result["events"], "transitions": result["changes"], "jumps": result["jumps"]}

    def upload(self, kind: str, owner: str, name: str, stream, length: int, fps: float | None, note: str,
               *, poses: list[str] | None = None, grid: object = "3x2") -> dict:
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
            if kind == "concept":
                from .concepts import import_sheet
                with self.lock:
                    return {"sheet": import_sheet(self.workspace, target, poses, grid)}
            if kind == "workflow":
                from .media import IMAGE_SUFFIXES, VIDEO_SUFFIXES, copy_durable, read_bgra, video_info
                if suffix in IMAGE_SUFFIXES:
                    read_bgra(target)
                    asset_type = "IMAGE"
                elif suffix in VIDEO_SUFFIXES:
                    video_info(target)
                    asset_type = "VIDEO"
                else:
                    raise ValueError("Workflow inputs must be supported images or videos")
                saved = resolve_asset(self.workspace, str(production_dir(self.workspace) / "workflows" / "inputs" / f"{uuid.uuid4().hex}{suffix}"))
                copy_durable(target, saved)
                return {"asset": {"type": asset_type, "path": saved.relative_to(self.workspace).as_posix()}}
        raise ValueError("Uploads belong to a pose, clip or concept sheet")

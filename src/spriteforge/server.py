"""Loopback-only editor. Files and graph writes belong to one selected workspace."""
from __future__ import annotations

import json
import socket
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .character_pack import load_character_pack
from .graph import layout_coordinates, validate_graph
from .production.api import ProductionApi
from .workspace import atomic_json, clip_frames, discover, png_frames, read_json, resolve_asset

WEB_ROOT = Path(__file__).parent / "web"
STATIC = {"review.js": "text/javascript", "review.css": "text/css", "preview-media.js": "text/javascript",
          "production.js": "text/javascript", "production-canvas.js": "text/javascript", "production.css": "text/css",
          "studio.js": "text/javascript", "studio-tools.js": "text/javascript", "studio.css": "text/css",
          "studio-clips.js": "text/javascript", "studio-clips.css": "text/css",
          "studio-compare.js": "text/javascript", "studio-compare.css": "text/css",
          "studio-expressions.js": "text/javascript", "studio-expressions.css": "text/css",
          "studio-review.js": "text/javascript", "studio-review.css": "text/css",
          "studio-behavior.js": "text/javascript", "studio-behavior.css": "text/css",
          "studio-export.js": "text/javascript", "studio-export.css": "text/css",
          "studio-workflows.js": "text/javascript", "studio-workflows.css": "text/css",
          "i18n/en.js": "text/javascript", "i18n/zh-CN.js": "text/javascript"}


class EditorHTTPServer(ThreadingHTTPServer):
    # Let the OS size the pending connection queue for a page's static-resource burst.
    request_queue_size = socket.SOMAXCONN


def make_server(workspace: Path, port: int = 7788, layout_path: Path | None = None) -> ThreadingHTTPServer:
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise ValueError("Workspace does not exist; run spriteforge init first")
    pack = load_character_pack(workspace) if (workspace / "runtime_manifest.json").exists() else None
    saved_positions = {}
    if layout_path is not None and not pack:
        raise ValueError("--layout is for runtime packs; authoring workspaces already own their saved coordinates")
    if pack:
        companion = workspace.with_name(workspace.name + ".graph-layout.json")
        source = layout_path if layout_path is not None else companion if companion.is_file() else None
        if source is not None:
            saved_positions = layout_coordinates(pack.graph, read_json(source))
        elif all("x" in n and "y" in n for n in pack.graph["nodes"]):
            saved_positions = layout_coordinates(pack.graph, pack.graph)
    indexed = {p for frames in pack.clip_paths.values() for p in frames} if pack else set()
    if pack:
        indexed.update(p for frames in pack.mouth_overlay_paths.values() for p in frames)
    lock = threading.Lock()
    production = None if pack else ProductionApi(workspace)

    class Handler(BaseHTTPRequestHandler):
        def send(self, status: int, content: bytes, mime: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def json(self, status: int, value: object) -> None:
            self.send(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode(), "application/json; charset=utf-8")

        def local_request(self) -> bool:
            port = self.server.server_port
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            origin = self.headers.get("Origin")
            return self.headers.get("Host") in hosts and (not origin or origin in {f"http://{h}" for h in hosts})

        def send_file(self, path: Path, mime: str) -> None:
            """Serve a file with single byte-range support so videos can seek."""
            size = path.stat().st_size
            start, end = 0, size - 1
            ranged = self.headers.get("Range", "")
            if ranged.startswith("bytes=") and "," not in ranged:
                first, _, last = ranged[6:].partition("-")
                start, end = (int(first), int(last) if last else size - 1) if first else (max(0, size - int(last)), size - 1)
                if not 0 <= start <= end < size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
            self.send_response(206 if ranged.startswith("bytes=") else 200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Accept-Ranges", "bytes")
            if ranged.startswith("bytes="):
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with open(path, "rb") as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = stream.read(min(remaining, 1 << 20))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

        def production_api(self) -> ProductionApi:
            if production is None:
                raise PermissionError("Production belongs to an authoring workspace, not a runtime pack")
            return production

        def do_GET(self) -> None:
            if not self.local_request():
                self.json(403, {"ok": False, "error": "Use the local editor URL"})
                return
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                if parsed.path in {"/", "/production", "/studio"}:
                    if parsed.path == "/production" or (parsed.path == "/" and production is not None and production.available()):
                        self.send_response(302)
                        self.send_header("Location", "/studio")
                        self.send_header("Content-Length", "0")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        return
                    page = "studio.html" if parsed.path == "/studio" else "review.html"
                    self.send(200, (WEB_ROOT / page).read_bytes(), "text/html; charset=utf-8")
                elif parsed.path == "/favicon.ico":
                    self.send(204, b"", "image/x-icon")
                elif parsed.path.startswith("/static/") and parsed.path[8:] in STATIC:
                    self.send(200, (WEB_ROOT / parsed.path[8:]).read_bytes(), STATIC[parsed.path[8:]])
                elif parsed.path == "/api/production":
                    self.json(200, self.production_api().overview())
                elif parsed.path == "/api/production/jobs":
                    self.json(200, {"ok": True, "jobs": self.production_api().job_list()})
                elif parsed.path == "/api/production/workflows" or parsed.path.startswith("/api/production/workflows/"):
                    self.json(200, {"ok": True, **self.production_api().workflow_get(parsed.path.removeprefix("/api/production/workflows"))})
                elif parsed.path == "/api/behavior/stats":
                    self.json(200, {"ok": True, **self.production_api().behavior_stats(
                        (qs.get("minutes") or ["10"])[0], (qs.get("seed") or ["1"])[0])})
                elif parsed.path == "/api/review/seam":
                    self.json(200, {"ok": True, **self.production_api().review_seam((qs.get("key") or [""])[0])})
                elif parsed.path == "/api/export/preflight":
                    self.json(200, {"ok": True, **self.production_api().export_preflight()})
                elif parsed.path == "/api/export/diff":
                    self.json(200, {"ok": True, **self.production_api().export_diff()})
                elif parsed.path == "/api/production/media":
                    self.send_file(*self.production_api().media((qs.get("path") or [""])[0]))
                elif parsed.path == "/api/production/input":
                    api = self.production_api()
                    data = api.pose_input(qs["pose"][0]) if qs.get("pose") else api.clip_input((qs.get("clip") or [""])[0], (qs.get("end") or [""])[0])
                    self.send(200, data, "image/png")
                elif parsed.path.startswith("/static/vendor/"):
                    name = parsed.path.rsplit("/", 1)[-1]
                    if name not in {"pixi.min.js", "pixi-basis-ktx2.global.js", "basis_transcoder.js", "basis_transcoder.wasm", "litegraph.core.js"}:
                        raise ValueError("Unknown browser dependency")
                    self.send(200, (WEB_ROOT / "vendor" / name).read_bytes(), "application/wasm" if name.endswith(".wasm") else "text/javascript")
                elif parsed.path == "/api/projects":
                    sources = [{"id": "runtime", "label": f"KTX2 pack: {pack.manifest['displayName']} (read only)",
                                "states": [{"id": label, "label": label, "root": label, "clips": {"loop": len(frames)}}
                                           for label, frames in pack.clip_paths.items()]}] if pack else discover(workspace)
                    self.json(200, {"ok": True, "readOnly": bool(pack), "sources": sources})
                elif parsed.path == "/api/graph":
                    path = resolve_asset(workspace, "graph_config.json")
                    with lock:
                        graph = pack.graph if pack else read_json(path) if path.exists() else {"nodes": [], "edges": []}
                    if pack:
                        graph = {"nodes": [{**n, "root": n["label"], "phase": pack.manifest["clips"][n["label"]]["phase"],
                                            "frameIntervalMs": pack.manifest["clips"][n["label"]]["frameIntervalMs"],
                                            "loopMode": pack.manifest["clips"][n["label"]]["loopMode"],
                                            **saved_positions.get(n["id"], {})}
                                           for n in pack.graph["nodes"]], "edges": pack.graph["edges"]}
                    self.json(200, {"ok": True, "graph": graph, "layoutAvailable": not pack or bool(saved_positions)})
                elif parsed.path == "/api/clips":
                    if pack:
                        label = (qs.get("root") or [""])[0]
                        if label not in pack.clip_paths:
                            raise ValueError("Unknown manifest clip")
                        clip = pack.manifest["clips"][label]
                        self.json(200, {"ok": True, "layout": "runtime_ktx2", "root": label, "state_label": label,
                                       "clips": {label: {**clip, "role": clip["phase"], "path": label,
                                                         "frames": [p.relative_to(workspace).as_posix() for p in pack.clip_paths[label]]}}})
                        return
                    root = resolve_asset(workspace, (qs.get("root") or [""])[0])
                    clips = {}
                    candidates = [("flat", root)] if png_frames(workspace, root) else [(p, root / p) for p in ("in", "loop", "out")]
                    for phase, directory in candidates:
                        frames = png_frames(workspace, directory)
                        if frames:
                            clips[f"{root.name}/{phase}"] = {"role": phase, "path": directory.relative_to(workspace).as_posix(),
                                "frames": [p.relative_to(workspace).as_posix() for p in frames]}
                    if not clips:
                        raise ValueError("No PNG frames here. Select an exact frame folder or a folder containing in/loop/out")
                    self.json(200, {"ok": True, "layout": "flat" if candidates[0][0] == "flat" else "legacy_in_loop_out",
                                    "root": root.relative_to(workspace).as_posix(), "state_label": root.name, "clips": clips})
                elif parsed.path == "/api/report":
                    if pack:
                        raise ValueError("Image QA requires authoring PNG frames; KTX2 review uses manifest-indexed playback")
                    root = resolve_asset(workspace, (qs.get("root") or [""])[0])
                    # Check all assets before handing them to the optional image-analysis library.
                    for frame in root.rglob("*.png"):
                        resolve_asset(workspace, str(frame))
                    try:
                        from .qa import build_report
                    except ImportError as exc:
                        raise ValueError('QA needs the optional dependencies: pip install ".[qa]"') from exc
                    self.json(200, {"ok": True, "report": build_report(root)})
                elif parsed.path == "/api/mouth_masks":
                    if pack:
                        self.json(200, {"ok": True, "expressions": {}})
                        return
                    # Authoring-only overlay preview; no runtime or legacy installation lookup.
                    path = resolve_asset(workspace, "spriteforge_mouth_config.json")
                    raw = read_json(path) if path.exists() else {}
                    expressions = {}
                    for label, cfg in raw.get("expressions", {}).items():
                        frames, openness = [], []
                        for key, value in (("half", .65), ("full", 1.0)):
                            ref = cfg.get("speaking_frames", {}).get(key)
                            if ref:
                                frame = resolve_asset(workspace, ref)
                                if not frame.is_file() or frame.suffix.lower() != ".png":
                                    raise ValueError(f"Missing PNG mouth frame for {label}")
                                frames.append("/frame?path=" + urllib.parse.quote(frame.relative_to(workspace).as_posix()))
                                openness.append(value)
                        expressions[label] = {**{k: cfg[k] for k in ("cx", "cy", "width", "height", "curve") if k in cfg},
                            "frameUrls": frames, "openness": openness, "closed_frame_idx": -1,
                            "open_frame_idx": len(frames) - 1, "sf": True}
                    self.json(200, {"ok": True, "expressions": expressions})
                elif parsed.path == "/frame":
                    frame = resolve_asset(workspace, (qs.get("path") or [""])[0])
                    if not frame.is_file() or (frame not in indexed if pack else frame.suffix.lower() != ".png"):
                        raise ValueError("Frame is not an indexed texture or workspace PNG")
                    self.send(200, frame.read_bytes(), "image/ktx2" if pack else "image/png")
                else:
                    self.json(404, {"ok": False, "error": "Not found"})
            except PermissionError as exc:
                self.json(409, {"ok": False, "error": str(exc)})
            except (ValueError, OSError, KeyError, TypeError, RuntimeError, ImportError) as exc:
                self.json(400, {"ok": False, "error": str(exc)})

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            upload = parsed.path in {"/api/production/upload", "/api/production/concepts/import"}
            expected = "application/octet-stream" if upload else "application/json"
            if not self.local_request() or self.headers.get_content_type() != expected:
                self.json(403, {"ok": False, "error": "Writes require a local request with the expected content type"})
                return
            if parsed.path.startswith("/api/production/"):
                self.production_post(parsed, upload)
                return
            if self.path not in {"/api/graph", "/api/validate", "/api/preview-node", "/api/preview-route"}:
                self.json(404, {"ok": False, "error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 2_000_000:
                    raise ValueError("Invalid graph request size")
                raw = json.loads(self.rfile.read(length))
                if self.path == "/api/preview-route":
                    if not isinstance(raw, dict) or not isinstance(raw.get("route"), list) or not raw["route"] \
                            or not all(isinstance(node_id, str) for node_id in raw["route"]):
                        raise ValueError("Preview route needs a non-empty list of node ids")
                    graph = pack.graph if pack else validate_graph(workspace, raw.get("graph"))
                    by_id = {node["id"]: node for node in graph["nodes"]}
                    segments = {}
                    for node_id in dict.fromkeys(raw["route"]):
                        if node_id not in by_id:
                            raise ValueError("Unknown route node")
                        node = by_id[node_id]
                        if pack:
                            clip = pack.manifest["clips"][node["label"]]
                            node = {**node, "frameIntervalMs": clip["frameIntervalMs"], "loopMode": clip["loopMode"]}
                            frames = pack.clip_paths[node["label"]]
                        else:
                            frames = clip_frames(workspace, node)
                        segments[node_id] = {"node": node, "frames": [p.relative_to(workspace).as_posix() for p in frames]}
                    self.json(200, {"ok": True, "segments": [segments[node_id] for node_id in raw["route"]]})
                    return
                if pack:
                    if self.path != "/api/preview-node":
                        self.json(409, {"ok": False, "error": "Runtime packs are read-only. Edit the authoring workspace instead"})
                        return
                    node = next((n for n in pack.graph["nodes"] if n["id"] == raw.get("nodeId")), None)
                    if node is None:
                        raise ValueError("Unknown runtime node")
                    clip = pack.manifest["clips"][node["label"]]
                    self.json(200, {"ok": True, "node": {**node, "frameIntervalMs": clip["frameIntervalMs"], "loopMode": clip["loopMode"]},
                                   "frames": [p.relative_to(workspace).as_posix() for p in pack.clip_paths[node["label"]]]})
                    return
                graph = validate_graph(workspace, raw.get("graph") if self.path == "/api/preview-node" else raw)
                if self.path == "/api/graph":
                    with lock:
                        atomic_json(resolve_asset(workspace, "graph_config.json"), graph)
                if self.path == "/api/preview-node":
                    node = next((n for n in graph["nodes"] if n["id"] == raw.get("nodeId")), None)
                    if node is None:
                        raise ValueError("Unknown node")
                    self.json(200, {"ok": True, "node": node,
                                   "frames": [p.relative_to(workspace).as_posix() for p in clip_frames(workspace, node)]})
                else:
                    self.json(200, {"ok": True, "graph": graph})
            except (ValueError, OSError, KeyError, TypeError) as exc:
                self.json(400, {"ok": False, "error": str(exc)})

        def production_post(self, parsed: urllib.parse.ParseResult, upload: bool) -> None:
            try:
                api = self.production_api()
                length = int(self.headers.get("Content-Length", "0"))
                if upload:
                    qs = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
                    fps = float(qs["fps"]) if qs.get("fps") else None
                    if parsed.path == "/api/production/concepts/import":
                        result = api.upload("concept", "", qs.get("name", ""), self.rfile, length, None, "",
                                            poses=qs.get("poses", "").split(","), grid=qs.get("grid", "3x2"))
                    else:
                        result = api.upload(qs.get("kind", ""), qs.get("owner", ""), qs.get("name", ""), self.rfile,
                                            length, fps, qs.get("note", ""))
                else:
                    if not 0 < length <= 2_000_000:
                        raise ValueError("Invalid request size")
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict):
                        raise ValueError("Request body must be a JSON object")
                    route = parsed.path.removeprefix("/api/production/")
                    try:
                        result = api.post(route, body)
                    except KeyError as exc:
                        if exc.args == (route,):
                            self.json(404, {"ok": False, "error": "Not found"})
                            return
                        raise
                self.json(200, {"ok": True, **result})
            except PermissionError as exc:
                self.json(409, {"ok": False, "error": str(exc)})
            except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
                self.json(400, {"ok": False, "error": str(exc)})

        def log_message(self, *args) -> None:
            pass

    return EditorHTTPServer(("127.0.0.1", port), Handler)


def serve(workspace: Path, port: int, no_browser: bool, layout_path: Path | None = None) -> None:
    with make_server(workspace, port, layout_path) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"SpriteForge: {url}\nWorkspace: {workspace.resolve()}", flush=True)
        if not no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

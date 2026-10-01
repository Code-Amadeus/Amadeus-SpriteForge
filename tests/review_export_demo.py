"""Serve a disposable review/export browser fixture; encoding is a local fake."""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from production_demo import main as build
from spriteforge.production.clips import import_clip_take
from spriteforge.production.render import render_take
from spriteforge.production.tools import load_tools, save_tools
from spriteforge.server import make_server
from spriteforge.workspace import atomic_json, read_json
from spriteforge.production.media import read_bgra, write_png


target = Path(sys.argv[1])
build(target)
workspace = target / "studio ws"
take = import_clip_take(workspace, "smile_in", target / "smile_in", fps=30)
render_take(workspace, "smile_in", take["id"], log=lambda *_: None)

render_file = workspace / "production/clips/idle_loop/output/render.json"
record = read_json(render_file)
record["qa"]["checks"].append({"check": "fixture-watch", "level": "watch", "message": "Synthetic review note"})
record["qa"]["status"] = "watch"
atomic_json(render_file, record)
graph = read_json(workspace / "graph_config.json")
start = next(node for node in graph["nodes"] if node["label"] == "idle_loop")
end = next(node for node in graph["nodes"] if node["label"] == "smile_talk")
graph["edges"] = [{"id": "fixture-seam", "from": start["id"], "to": end["id"], "prob": 1}]
atomic_json(workspace / "graph_config.json", graph)
first = workspace / "production/clips/smile_talk/output/loop/000000.png"
image = read_bgra(first)[0]
write_png(first, cv2.warpAffine(image, np.float32([[1, 0, 18], [0, 1, 0]]), image.shape[1::-1], borderValue=(0, 0, 0, 0)))

tools = load_tools(workspace)
tools["toktx"] = "browser-test-encoder"
save_tools(workspace, tools)
real_which, real_run = shutil.which, subprocess.run


def run(command, **kwargs):
    if command[0] != "browser-test-encoder":
        return real_run(command, **kwargs)
    destination = Path(command[-2]).resolve()
    assert destination.is_relative_to(workspace.resolve())
    destination.write_bytes(b"\xabKTX 20\xbb\r\n\x1a\n" + hashlib.sha256(Path(command[-1]).read_bytes()).digest())
    return SimpleNamespace(returncode=0, stderr="")


shutil.which = lambda command, *args, **kwargs: command if command == "browser-test-encoder" else real_which(command, *args, **kwargs)
subprocess.run = run
with make_server(workspace, 0) as server:
    print(f"http://127.0.0.1:{server.server_port}", flush=True)
    server.serve_forever()

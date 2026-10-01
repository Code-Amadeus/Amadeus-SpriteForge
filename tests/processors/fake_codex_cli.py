"""A deterministic Codex-shaped image process. No network, credentials or real CLI."""
import hashlib
import json
import os
import shutil
import struct
import sys
import time
import uuid
from pathlib import Path


args = sys.argv[1:]
folder = Path(os.environ["FAKE_CODEX_STATE"])
folder.mkdir(parents=True, exist_ok=True)
images = [Path(args[index + 1]) for index, arg in enumerate(args[:-1]) if arg == "--image"]
prompt = sys.stdin.read()
record = {"args": args, "cwd": str(Path.cwd()), "prompt": prompt,
          "images": [{"name": image.name, "sha256": hashlib.sha256(image.read_bytes()).hexdigest()} for image in images],
          "apiEnvironmentPresent": any(name in os.environ for name in ("OPENAI_API_KEY", "CODEX_API_KEY"))}
with (folder / "calls.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(record) + "\n")
mode = os.environ.get("FAKE_CODEX_MODE", "success")
if mode in {"auth", "quota"}:
    print("Not logged in" if mode == "auth" else "Plan image quota exhausted", file=sys.stderr)
    raise SystemExit(1)
if mode == "timeout":
    time.sleep(3)
thread_id = str(uuid.uuid4())
root = Path(os.environ["CODEX_HOME"]) / "generated_images"
current = root / thread_id
current.mkdir(parents=True, exist_ok=True)
if mode != "no-thread":
    print(json.dumps({"type": "thread.started", "thread_id": thread_id}), flush=True)
if mode == "duplicate-thread":
    print(json.dumps({"type": "thread.started", "thread_id": str(uuid.uuid4())}), flush=True)
output = current / ("exec-" + str(uuid.uuid4()) + ".png")
if mode == "other-thread":
    output = root / str(uuid.uuid4()) / output.name
    output.parent.mkdir(parents=True, exist_ok=True)
if mode == "outside":
    output = folder / "outside.png"
if mode == "bad-png":
    output.write_bytes(b"not an image")
elif mode == "truncated-png":
    output.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR")
elif mode == "symlink":
    output.symlink_to(Path(os.environ["FAKE_CODEX_IMAGE"]))
else:
    shutil.copyfile(os.environ["FAKE_CODEX_IMAGE"], output)
schema_file = Path(args[args.index("--output-schema") + 1])
schema = json.loads(schema_file.read_text(encoding="utf-8"))
record = {"schema": schema}
(folder / "schema-seen.json").write_text(json.dumps(record), encoding="utf-8")
source = Path(os.environ["FAKE_CODEX_IMAGE"]).read_bytes()
width, height = struct.unpack(">II", source[16:24])
answer = {"image_path": str(output) if mode != "no-image" else None, "width": width, "height": height, "error": None}
if mode == "narration-error":
    answer.update(width=9999, height=1, error="Requested dimensions were not honored")
if mode == "no-image":
    answer.update(width=None, height=None, error="No image generated")
result = Path(args[args.index("--output-last-message") + 1])
result.write_text(json.dumps(answer), encoding="utf-8")
print(json.dumps({"type": "turn.completed"}), flush=True)

"""Stand-in for Wan's CLI (@wan-ai/cli) in adapter tests, answering with the CLI's JSON shapes.

State lives in the folder named by FAKE_WAN_STATE: every call is appended to calls.jsonl,
the file `logged_in` marks a login, `credits` holds the balance (a submission costs 10),
and `polls` counts result queries (the first reports processing). The video named by
FAKE_WAN_VIDEO is what a saved result contains.
"""
import json
import os
import shutil
import sys
from pathlib import Path

state = Path(os.environ["FAKE_WAN_STATE"])
args = sys.argv[1:]
with open(state / "calls.jsonl", "a", encoding="utf-8") as log:
    log.write(json.dumps({"args": args, "cwd": os.getcwd(),
                          "env": {k: os.environ.get(k) for k in ("WAN_SKIP_SKILL_INSTALL", "WAN_LANG")}}) + "\n")


def out(value: dict, code: int = 0) -> None:
    print(json.dumps(value))
    sys.exit(code)


def flag(name: str) -> str | None:
    return args[args.index(name) + 1] if name in args else None


credits = int((state / "credits").read_text())
if args[:2] == ["auth", "status"]:
    if (state / "logged_in").exists():
        out({"ok": True, "site": "intl", "accountId": "demo"})
    out({"ok": False, "errorMsg": "Wan AccessKey is not configured. Run `wan auth login` first."}, 1)
if args[:1] == ["credits"]:
    out({"ok": True, "credits": credits})
if args[:1] == ["frame2video"]:
    for name in ("--first-frame", "--last-frame"):
        if name in args:
            shutil.copy(flag(name), state / Path(flag(name)).name)  # what was uploaded
    (state / "credits").write_text(str(credits - 10))
    out({"taskId": "wan-cli-1", "request": {"deductMode": "credit_mode", "taskType": "image_to_video"}})
if args[:2] == ["result", "get"]:
    polls = int((state / "polls").read_text()) if (state / "polls").exists() else 0
    (state / "polls").write_text(str(polls + 1))
    status = 1 if polls == 0 else 2
    result = {"ok": status == 2, "taskId": args[2], "status": status, "statusLabel": "processing" if status == 1 else "succeeded",
              "result": [{"downloadUrl": "https://example.invalid/video.mp4"}]}
    if "--save" in args and status == 2:
        target = Path(flag("--save-dir")) / "Wan_Image_to_Video_test.mp4"
        shutil.copy(os.environ["FAKE_WAN_VIDEO"], target)
        result["savedFiles"] = [{"url": "https://example.invalid/video.mp4", "source": "downloadUrl", "watermark": "without",
                                 "index": 0, "fileName": target.name, "path": str(target)}]
    out(result)
out({"ok": False, "errorMsg": f"unknown command {args}"}, 2)

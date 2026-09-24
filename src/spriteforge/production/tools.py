"""Machine-local tools: ffmpeg, external frame processors and provider endpoints.

Heavy models such as anime segmentation or GMFSS stay outside this package. A
processor is a command that reads one directory of PNG frames and writes another:

- ``alpha``: same file names and sizes, RGBA output.
- ``interpolate``: ``N * factor`` frames when ``{wrap}`` is 1 (the last frame
  interpolates toward the first), otherwise ``(N - 1) * factor + 1``.

Command arguments may use ``{input}``, ``{output}``, ``{factor}`` and ``{wrap}``.
Outputs are checked before they are used. API keys are only read from the
environment variable a provider names, never from this file.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..workspace import atomic_json, read_json
from .records import production_dir

TOOLS_FORMAT = "spriteforge.production.tools.v1"


def default_tools() -> dict:
    return {"format": TOOLS_FORMAT, "ffmpeg": "ffmpeg", "alpha": None, "interpolate": None,
            "providers": {
                "wan": {"baseUrl": "https://dashscope.aliyuncs.com/api/v1", "model": "wan2.7-i2v-2026-04-25",
                        "apiKeyEnv": "DASHSCOPE_API_KEY", "pollSeconds": 10, "timeoutSeconds": 1800},
                "seedance": {"baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
                             "model": "doubao-seedance-1-5-pro-251215", "apiKeyEnv": "ARK_API_KEY",
                             "pollSeconds": 5, "timeoutSeconds": 1800}}}


def load_tools(workspace: Path) -> dict:
    path = production_dir(workspace) / "tools.json"
    tools = read_json(path) if path.is_file() else default_tools()
    if tools.get("format") != TOOLS_FORMAT:
        raise ValueError("Unsupported production/tools.json format")
    for name in ("alpha", "interpolate"):
        spec = tools.get(name)
        if spec is not None and (not isinstance(spec, dict) or not isinstance(spec.get("command"), list)
                                 or not spec["command"] or not all(isinstance(p, str) for p in spec["command"])):
            raise ValueError(f"tools.json '{name}' must be null or an object with a non-empty 'command' list")
    return tools


def save_tools(workspace: Path, tools: dict) -> None:
    atomic_json(production_dir(workspace) / "tools.json", tools)


def run_processor(tools: dict, name: str, source: Path, target: Path, **values: object) -> None:
    spec = tools.get(name)
    if not spec:
        raise ValueError(f"No '{name}' processor is configured in production/tools.json")
    target.mkdir(parents=True, exist_ok=True)
    substitutions = {"{input}": str(source), "{output}": str(target),
                     **{"{" + key + "}": str(value) for key, value in values.items()}}
    command = []
    for part in spec["command"]:
        for token, value in substitutions.items():
            part = part.replace(token, value)
        command.append(part)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=int(spec.get("timeoutSeconds", 7200)))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"The {name} processor could not run: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-600:]
        raise ValueError(f"The {name} processor failed with exit code {result.returncode}: {detail}")

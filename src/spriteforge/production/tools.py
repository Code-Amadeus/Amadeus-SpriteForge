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
from .records import load_character, production_dir

TOOLS_FORMAT = "spriteforge.production.tools.v1"
UI_DEFAULTS = {"conceptProvider": "qwen-image", "stillProvider": "qwen-image", "batchConfirmThreshold": 3}


def default_tools() -> dict:
    return {"format": TOOLS_FORMAT, "ffmpeg": "ffmpeg", "alpha": None, "interpolate": None,
            "defaults": dict(UI_DEFAULTS),
            "providers": {
                "wan": {"baseUrl": "https://dashscope.aliyuncs.com/api/v1", "model": "wan2.7-i2v-2026-04-25",
                        "apiKeyEnv": "DASHSCOPE_API_KEY", "pollSeconds": 10, "timeoutSeconds": 1800},
                "seedance": {"baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
                             "model": "doubao-seedance-1-5-pro-251215", "apiKeyEnv": "ARK_API_KEY",
                             "pollSeconds": 5, "timeoutSeconds": 1800},
                # Wan's own CLI, billed to the wan.video account's credits. On Windows point the
                # command at node and the package's dist/index.js: a .cmd shim mangles prompts.
                "wan-cli": {"command": ["wan"], "model": "wan3.0", "audioOutput": False,
                            "pollSeconds": 10, "timeoutSeconds": 1800, "requestSeconds": 300},
                "qwen-image": {"baseUrl": "https://dashscope.aliyuncs.com/api/v1", "model": "qwen-image-edit-plus",
                               "apiKeyEnv": "DASHSCOPE_API_KEY", "requestSeconds": 300},
                "seedream": {"baseUrl": "https://ark.cn-beijing.volces.com/api/v3", "model": "doubao-seedream-4-0-250828",
                             "apiKeyEnv": "ARK_API_KEY", "requestSeconds": 300, "size": "match"}}}


def load_tools(workspace: Path) -> dict:
    path = production_dir(workspace) / "tools.json"
    tools = read_json(path) if path.is_file() else default_tools()
    if tools.get("format") != TOOLS_FORMAT:
        raise ValueError("Unsupported production/tools.json format")
    # Adapters added later appear with their defaults; entries in the file always win.
    tools["providers"] = {**default_tools()["providers"], **(tools.get("providers") or {})}
    tools["defaults"] = {**UI_DEFAULTS, **(tools.get("defaults") or {})}
    for name in ("alpha", "interpolate"):
        spec = tools.get(name)
        if spec is not None and (not isinstance(spec, dict) or not isinstance(spec.get("command"), list)
                                 or not spec["command"] or not all(isinstance(p, str) for p in spec["command"])):
            raise ValueError(f"tools.json '{name}' must be null or an object with a non-empty 'command' list")
    return tools


def save_tools(workspace: Path, tools: dict) -> None:
    atomic_json(production_dir(workspace) / "tools.json", tools)


def ui_settings(tools: dict) -> dict:
    """Expose only documented UI settings, never provider credentials or commands."""
    defaults = tools.get("defaults") or {}
    return {"defaults": {key: defaults.get(key, value) for key, value in UI_DEFAULTS.items()},
            "amadeus": {"packDir": (tools.get("amadeus") or {}).get("packDir")}}


def set_ui_defaults(workspace: Path, changes: object) -> dict:
    """Update the three UI defaults while retaining machine-local tool configuration."""
    from .providers import IMAGE_PROVIDERS

    if not isinstance(changes, dict) or set(changes) - UI_DEFAULTS.keys():
        raise ValueError("Settings only accept conceptProvider, stillProvider and batchConfirmThreshold")
    for key, value in changes.items():
        if key == "batchConfirmThreshold":
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("batchConfirmThreshold must be a positive integer")
        elif not isinstance(value, str) or value not in IMAGE_PROVIDERS:
            raise ValueError(f"{key} must name a supported image provider: {', '.join(IMAGE_PROVIDERS)}")
    tools = load_tools(workspace)
    if not changes:
        return ui_settings(tools)["defaults"]
    load_character(workspace)
    tools["defaults"].update(changes)
    save_tools(workspace, tools)
    return ui_settings(tools)["defaults"]


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

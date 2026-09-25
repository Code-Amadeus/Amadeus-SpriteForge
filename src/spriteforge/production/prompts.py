"""Versioned prompt blocks composed by templates.

A block keeps an append-only list of versions; editing a block adds a version
and never rewrites one that a take may have used. A template is an ordered list
of block ids, where ``@subject`` stands for the pose or clip's own block. A
render records the exact text, the version of every block and a hash, and it is
incomplete while any ``{{PLACEHOLDER: ...}}`` remains.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..workspace import atomic_json, read_json
from .records import now, production_dir

PROMPTS_FORMAT = "spriteforge.production.prompts.v1"
SUBJECT = "@subject"
PLACEHOLDER = re.compile(r"\{\{\s*PLACEHOLDER\s*:\s*(.*?)\s*\}\}", re.S)
VARIABLE = re.compile(r"\$\{([a-zA-Z_]+)\}")
VARIABLES = {"character", "pose", "description", "from", "to", "duration"}
BLOCK_ID = re.compile(r"[a-z0-9][a-z0-9_.-]{0,95}")

DEFAULT_BLOCKS = {
    "character": ("Identity and art style shared by every prompt",
                  "{{PLACEHOLDER: character identity, outfit and art style}}"),
    "still.edit": ("Edit of the base still into a pose or expression",
                   "{{PLACEHOLDER: keep canvas, framing, character size and head position identical to the input image}}"),
    "still.negative": ("Negative prompt for still edits", "{{PLACEHOLDER: negative prompt for still edits}}"),
    "video.invariants": ("Constraints shared by every video",
                         "{{PLACEHOLDER: camera locked, no zoom or crop, character scale and position locked, plain background}}"),
    "video.transition": ("Motion from the first frame to the last frame",
                         "{{PLACEHOLDER: smooth transition that starts on the first frame and ends exactly on the last frame}}"),
    "video.loop": ("Loop that returns to its first frame",
                   "{{PLACEHOLDER: subtle seamless loop whose last frame matches the first frame}}"),
    "video.negative": ("Negative prompt for videos", "{{PLACEHOLDER: negative prompt for videos}}"),
}
DEFAULT_TEMPLATES = {
    "still": {"blocks": ["character", "still.edit", SUBJECT], "negative": ["still.negative"]},
    "transition": {"blocks": ["character", "video.invariants", "video.transition", SUBJECT], "negative": ["video.negative"]},
    "loop": {"blocks": ["character", "video.invariants", "video.loop", SUBJECT], "negative": ["video.negative"]},
}


def _path(workspace: Path) -> Path:
    return production_dir(workspace) / "prompts.json"


def default_library() -> dict:
    stamp = now()
    return {"format": PROMPTS_FORMAT,
            "blocks": {bid: {"description": description, "versions": [{"version": 1, "text": text, "createdAt": stamp}]}
                       for bid, (description, text) in DEFAULT_BLOCKS.items()},
            "templates": {tid: {"blocks": list(t["blocks"]), "negative": list(t["negative"])} for tid, t in DEFAULT_TEMPLATES.items()}}


def validate_library(library: object) -> dict:
    if not isinstance(library, dict) or library.get("format") != PROMPTS_FORMAT:
        raise ValueError("Unsupported prompt library format")
    blocks, templates = library.get("blocks"), library.get("templates")
    if not isinstance(blocks, dict) or not isinstance(templates, dict):
        raise ValueError("Prompt library requires blocks and templates")
    for bid, block in blocks.items():
        versions = block.get("versions") if isinstance(block, dict) else None
        if not BLOCK_ID.fullmatch(str(bid)) or not isinstance(versions, list) or not versions:
            raise ValueError(f"Prompt block {bid!r} needs a valid id and at least one version")
        if [v.get("version") for v in versions] != list(range(1, len(versions) + 1)):
            raise ValueError(f"Prompt block {bid!r} versions must be numbered 1..n")
        if any(not isinstance(v.get("text"), str) for v in versions):
            raise ValueError(f"Prompt block {bid!r} has a version without text")
    for tid, template in templates.items():
        parts = [*(template.get("blocks") or []), *(template.get("negative") or [])] if isinstance(template, dict) else None
        if not parts or any(p != SUBJECT and p not in blocks for p in parts):
            raise ValueError(f"Prompt template {tid!r} references an unknown block")
    return library


def load_library(workspace: Path) -> dict:
    path = _path(workspace)
    if not path.is_file():
        raise ValueError("This workspace has no prompt library; run 'spriteforge production init'")
    return validate_library(read_json(path))


def save_library(workspace: Path, library: dict) -> None:
    atomic_json(_path(workspace), validate_library(library))


def current(library: dict, block_id: str) -> dict:
    block = library["blocks"].get(block_id)
    if block is None:
        raise ValueError(f"Unknown prompt block: {block_id}")
    return block["versions"][-1]


def set_block(library: dict, block_id: str, text: str, description: str | None = None) -> int:
    """Append a version when the text changes; returns the current version number."""
    if not BLOCK_ID.fullmatch(block_id) or not isinstance(text, str):
        raise ValueError("A prompt block needs a valid id and text")
    unknown = sorted(set(VARIABLE.findall(text)) - VARIABLES)
    if unknown:
        raise ValueError(f"Unknown prompt variable(s) {', '.join(unknown)}; use {', '.join(sorted(VARIABLES))}")
    block = library["blocks"].setdefault(block_id, {"description": description or "", "versions": []})
    if description is not None:
        block["description"] = description
    if block["versions"] and block["versions"][-1]["text"] == text:
        return block["versions"][-1]["version"]
    block["versions"].append({"version": len(block["versions"]) + 1, "text": text, "createdAt": now()})
    return block["versions"][-1]["version"]


def ensure_subject(library: dict, block_id: str, hint: str) -> None:
    if block_id not in library["blocks"]:
        set_block(library, block_id, "{{PLACEHOLDER: " + hint + "}}", f"Subject of {block_id}")


def render(library: dict, template_id: str, subject: str, variables: dict[str, object]) -> dict:
    template = library["templates"].get(template_id)
    if template is None:
        raise ValueError(f"Unknown prompt template: {template_id}")
    used: dict[str, int] = {}

    def compose(parts: list[str]) -> str:
        texts = []
        for part in parts:
            block_id = subject if part == SUBJECT else part
            version = current(library, block_id)
            used[block_id] = version["version"]
            text = VARIABLE.sub(lambda m: substitute(m.group(1)), version["text"]).strip()
            if text:
                texts.append(text)
        return "\n\n".join(texts)

    def substitute(name: str) -> str:
        if name not in variables:
            raise ValueError(f"Prompt uses unknown variable ${{{name}}}; available: {', '.join(sorted(variables))}")
        return str(variables[name])

    text, negative = compose(template["blocks"]), compose(template.get("negative") or [])
    placeholders = [m.group(1) for m in PLACEHOLDER.finditer(text + "\n" + negative)]
    digest = hashlib.sha256(f"{text}\0{negative}".encode()).hexdigest()
    return {"template": template_id, "text": text, "negative": negative, "blocks": used,
            "placeholders": placeholders, "complete": not placeholders, "sha256": digest, "renderedAt": now()}


def pose_prompt(library: dict, character: dict, pose: dict) -> dict:
    return render(library, pose["prompt"]["template"], pose["prompt"]["subject"],
                  {"character": character["displayName"], "pose": pose["id"], "description": pose.get("description", "")})


def clip_prompt(library: dict, character: dict, clip: dict) -> dict:
    return render(library, clip["prompt"]["template"], clip["prompt"]["subject"],
                  {"character": character["displayName"], "from": clip["from"], "to": clip["to"],
                   "duration": clip["generation"]["durationS"]})


def require_complete(rendered: dict) -> None:
    if not rendered["complete"]:
        hints = "; ".join(rendered["placeholders"][:4])
        raise ValueError(f"The prompt still has {len(rendered['placeholders'])} placeholder(s) ({hints}). "
                         "Write them with 'spriteforge production prompt set' before paid generation")

"""Fixed workflow operations over SpriteForge's existing production primitives.

Assets identify immutable bytes and host provenance. Local transformations retain
conceptual origin; only an edit of the approved normal base can produce a normal
generated image. Output operations create candidates, never decisions or renders.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from copy import deepcopy
from pathlib import Path

import cv2

from ..workspace import read_json, resolve_asset
from . import concepts, prompts
from .media import (IMAGE_SUFFIXES, VIDEO_SUFFIXES, copy_durable, encode_png, image_suffix,
                    media_frames, read_bgra, sorted_pngs, video_info, write_durable, write_png)
from .providers import IMAGE_PROVIDERS, PROVIDERS, ImageJob, VideoJob, get_image_provider, get_provider
from .records import (canvas_size, load_character, load_owner, load_take, save_take, still_path,
                      take_dir, take_media_frames)
from .tools import load_tools, run_processor

TYPES = ["IMAGE", "IMAGES", "VIDEO", "FRAMES", "TEXT", "NUMBER", "POSE", "CLIP"]
MEDIA = ["IMAGE", "VIDEO", "FRAMES"]
OUTPUT_MEDIA = ["IMAGE", "FRAMES"]


def _parameter(type_, default=None, *, required=False, choices=None, min_=None, max_=None):
    spec = {"type": type_}
    if default is not None:
        spec["default"] = default
    if required:
        spec["required"] = True
    if choices is not None:
        spec["choices"] = choices
    if min_ is not None:
        spec["min"] = min_
    if max_ is not None:
        spec["max"] = max_
    return spec


def _node(label, inputs=None, outputs=None, params=None, *, paid=False):
    return {"label": label, "inputs": {port: {"type": type_, "required": required}
            for port, (type_, required) in (inputs or {}).items()}, "outputs": outputs or {},
            "params": params or {}, "paid": paid}


_string = lambda default="": _parameter("string", default)
_required = lambda: _parameter("string", required=True)
_positive = lambda default: _parameter("number", default, min_=0.001)
_integer = lambda default, min_=0: _parameter("integer", default, min_=min_)
_grid = _parameter("string", "3x2", choices=["3x2", "2x2"])
_pose = {"pose": _required()}
_image_provider = _parameter("string", "qwen-image", choices=list(IMAGE_PROVIDERS))
REGISTRY = {
    "base-still": _node("Base still", outputs={"image": "IMAGE", "pose": "POSE"}),
    "approved-still": _node("Approved still", outputs={"image": "IMAGE", "pose": "POSE"}, params=_pose),
    "concept-cell": _node("Concept cell", outputs={"image": "IMAGE"}, params={"sheet": _required(), "cell": _integer(0)}),
    "clip-take": _node("Clip take", outputs={"media": ["VIDEO", "FRAMES"], "clip": "CLIP"}, params={"clip": _required(), "take": _required()}),
    "load-image": _node("Load image", outputs={"image": "IMAGE"}, params={"path": _required()}),
    "load-video": _node("Load video", outputs={"video": "VIDEO"}, params={"path": _required()}),
    "text": _node("Text", outputs={"text": "TEXT"}, params={"text": _string()}),
    "prompt-template": _node("Prompt template", outputs={"text": "TEXT"}, params={
        "template": _parameter("string", "still", choices=["still", "still-reference", "transition", "loop", "concept"]),
        "pose": _string(), "clip": _string(), "poses": _parameter("strings", []), "grid": _grid}),
    "join-text": _node("Join text", {"a": ("TEXT", True), "b": ("TEXT", True)}, {"text": "TEXT"}, {"separator": _string("\n\n")}),
    "image-edit": _node("Image edit", {"image": ("IMAGE", True), "reference": ("IMAGE", False), "prompt": ("TEXT", True)},
        {"image": "IMAGE"}, {"provider": _image_provider, "width": _integer(0), "height": _integer(0)}, paid=True),
    "concept-sheet": _node("Concept sheet", {"image": ("IMAGE", True), "prompt": ("TEXT", True)}, {"image": "IMAGE"},
        {"provider": _image_provider, "grid": _grid}, paid=True),
    "video-from-frames": _node("Video from frames", {"first": ("IMAGE", True), "last": ("IMAGE", False), "prompt": ("TEXT", True)},
        {"video": "VIDEO"}, {"provider": _parameter("string", "wan-cli", choices=list(PROVIDERS)),
            "durationS": _integer(5, 1), "resolution": _parameter("string", "720P", choices=["480P", "720P", "1080P"]),
            "seed": {"type":"integer","default":None,"nullable":True,"min":0},
            "inputScale": _parameter("number",1.0,min_=0.5,max_=1.0)}, paid=True),
    "split-grid": _node("Split grid", {"image": ("IMAGE", True)}, {"images": "IMAGES"}, {"grid": _grid}),
    "select-image": _node("Select image", {"images": (["IMAGES","FRAMES"], True)}, {"image": "IMAGE"}, {"index": _integer(0)}),
    "matte": _node("Matte", {"media": (MEDIA, True)}, {"media": OUTPUT_MEDIA}),
    "normalize": _node("Normalize onto canvas", {"media": (MEDIA, True)}, {"media": OUTPUT_MEDIA},
        {"pose": _required(), "scale": _positive(1.0), "dx": _parameter("number", 0), "dy": _parameter("number", 0), "explicit": _parameter("boolean", False)}),
    "interpolate": _node("Interpolate", {"media": (["VIDEO","FRAMES"], True)}, {"media": "FRAMES"}, {"factor": _integer(2, 2)}),
    "reverse": _node("Reverse", {"media": (["VIDEO","FRAMES"], True)}, {"media": "FRAMES"}),
    "pingpong": _node("Pingpong", {"media": (["VIDEO","FRAMES"], True)}, {"media": "FRAMES"}),
    "trim": _node("Trim", {"media": (["VIDEO","FRAMES"], True)}, {"media": "FRAMES"}, {"start": _integer(0), "end": _integer(0)}),
    "scale": _node("Scale", {"media": (MEDIA, True)}, {"media": OUTPUT_MEDIA}, {"factor": _positive(1.0)}),
    "external-processor": _node("External processor", {"media": (MEDIA, True)}, {"media": OUTPUT_MEDIA}, {"processor": _required()}),
    "still-qa": _node("Still QA", {"image": ("IMAGE", True)}, {"image": "IMAGE", "qa": "TEXT"}, _pose),
    "preview": _node("Preview", {"media": (["IMAGE", "IMAGES", "VIDEO", "FRAMES"], True)}, {"media": ["IMAGE", "IMAGES", "VIDEO", "FRAMES"]}),
    "compare": _node("Compare", {"a": ("IMAGE", True), "b": ("IMAGE", True)}, {"a": "IMAGE", "b": "IMAGE", "report": "TEXT"}),
    "save-pose-take": _node("Save as pose take", {"image": ("IMAGE", True)}, {"pose": "POSE"}, {**_pose, "note": _string()}),
    "save-clip-take": _node("Save as clip take", {"media": (["VIDEO", "FRAMES"], True)}, {"clip": "CLIP"}, {"clip": _required(), "note": _string()}),
    "save-concept-sheet": _node("Save concept sheet", {"image": ("IMAGE", True)}, {"images": "IMAGES"}, {"poses": _parameter("strings", [], required=True), "grid": _grid}),
    "reroute": _node("Reroute", {"input": (TYPES, True)}, {"output": TYPES}, {"type": _parameter("string", "IMAGE", choices=TYPES)}),
}


def ports(kind: str, params: dict) -> dict:
    spec = deepcopy(REGISTRY[kind])
    if kind == "reroute":
        spec["inputs"]["input"]["type"] = params["type"]
        spec["outputs"]["output"] = params["type"]
    return {"inputs": spec["inputs"], "outputs": spec["outputs"]}


def _path(workspace: Path, value: str) -> Path:
    """Resolve only a workspace-relative asset, including through symlinks."""
    if not isinstance(value, str) or Path(value).is_absolute():
        raise ValueError("Workflow paths must be workspace-relative")
    return resolve_asset(workspace, value)


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _file(workspace: Path, path: Path, type_: str, *, provenance=None, **facts) -> dict:
    path = path.resolve()
    relative = path.relative_to(workspace.resolve()).as_posix()
    source = deepcopy(provenance or {})
    if relative.startswith("production/concepts/"):
        source["conceptual"] = True
    parts = Path(relative).parts
    if parts[:3] == ("production","workflows","runs") and len(parts) >= 6:
        receipt_file = workspace.joinpath(*parts[:5],"node.json")
        if receipt_file.is_file():
            receipt = read_json(receipt_file)
            if receipt.get("format") == "spriteforge.workflow.node.v1":
                conceptual = receipt.get("operation",{}).get("conceptual",False)
                for output in receipt.get("outputs",{}).values():
                    if relative in output.get("paths",[output.get("path")]):
                        conceptual = conceptual or output.get("provenance",{}).get("conceptual",False)
                if conceptual:
                    source["conceptual"] = True
    return {"type": type_, "path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "provenance": source, **facts}


def _images(workspace: Path, paths: list[Path], type_: str, *, provenance=None, **facts) -> dict:
    files = [_file(workspace, path, "IMAGE", provenance=provenance) for path in paths]
    return {"type": type_, "paths": [item["path"] for item in files], "sha256": _hash([item["sha256"] for item in files]),
            "provenance": deepcopy(provenance or {}), **facts}


def _text(text: str, *, snapshot=None, provenance=None) -> dict:
    return {"type": "TEXT", "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(), "provenance": provenance or {},
            **({"prompt": snapshot} if snapshot else {})}


def _record_asset(type_: str, owner: dict, *, take=None, provenance=None) -> dict:
    reference = {"kind": type_.lower(), "owner": owner["id"], **({"take": take["id"]} if take else {})}
    return {"type": type_, "record": reference, "sha256": _hash(reference), "provenance": provenance or {}}


def _processor_names(tools: dict) -> list[str]:
    return sorted(name for name, value in tools.items() if isinstance(value, dict) and isinstance(value.get("command"), list) and value["command"])


def public_registry(workspace: Path) -> list[dict]:
    tools = load_tools(workspace)
    result = []
    for kind, raw in REGISTRY.items():
        spec = {"kind": kind, **deepcopy(raw)}
        if kind == "external-processor":
            spec["params"]["processor"]["choices"] = _processor_names(tools)
        if spec["paid"]:
            spec["costType"] = "provider"
        result.append(spec)
    return result


def validate_params(workspace: Path, kind: str, params: object) -> dict:
    if kind not in REGISTRY:
        raise ValueError(f"Unknown workflow operation: {kind}")
    if not isinstance(params, dict) or set(params) - REGISTRY[kind]["params"].keys():
        raise ValueError(f"Unsupported parameters for {kind}")
    result = {}
    for key, spec in REGISTRY[kind]["params"].items():
        value = params.get(key, deepcopy(spec.get("default")))
        if value is None and spec.get("nullable"):
            result[key] = None
            continue
        type_ = spec["type"]
        valid = isinstance(value, str) if type_ == "string" else isinstance(value, bool) if type_ == "boolean" else \
            isinstance(value, list) and all(isinstance(item, str) for item in value) if type_ == "strings" else \
            isinstance(value, int) and not isinstance(value, bool) if type_ == "integer" else \
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        if not valid or spec.get("required") and not value:
            raise ValueError(f"{kind}.{key} needs {type_}")
        if "choices" in spec and value not in spec["choices"] or "min" in spec and value < spec["min"] or "max" in spec and value > spec["max"]:
            raise ValueError(f"Invalid {kind}.{key}")
        result[key] = value
    if "path" in result:
        source = _path(workspace, result["path"])
        suffixes = IMAGE_SUFFIXES if kind == "load-image" else VIDEO_SUFFIXES
        if not source.is_file() or source.suffix.lower() not in suffixes:
            raise ValueError(f"{kind} needs an existing supported file")
    if result.get("pose"):
        load_owner(workspace, "pose", result["pose"])
    if result.get("clip"):
        load_owner(workspace, "clip", result["clip"])
    if kind == "concept-cell":
        sheet = concepts.load_sheet(workspace, result["sheet"])
        concepts._cell(sheet, result["cell"])
        if sheet["state"] != "ready":
            raise ValueError("Concept sheet is not ready")
    if kind == "clip-take" and load_take(workspace, "clip", result["clip"], result["take"])["state"] != "ready":
        raise ValueError("Clip take is not ready")
    if kind == "external-processor" and result["processor"] not in _processor_names(load_tools(workspace)):
        raise ValueError("External processors must name a configured processor")
    if kind == "image-edit" and bool(result["width"]) != bool(result["height"]):
        raise ValueError("Image edit size needs both width and height, or neither")
    return result


def context(workspace: Path, kind: str, params: dict, inputs: dict | None = None) -> dict:
    """Fingerprint inputs owned by an operation; never expose tool secrets."""
    params = validate_params(workspace, kind, params)
    character, tools = load_character(workspace), load_tools(workspace)
    inputs = inputs or {}
    facts = {"owners": [], "revision": 1}
    if "path" in params:
        facts["source"] = _file(workspace, _path(workspace, params["path"]), "IMAGE" if kind == "load-image" else "VIDEO")
    if kind in {"base-still", "approved-still"}:
        pose_id = params.get("pose", character["basePose"])
        path, take = still_path(workspace, pose_id)
        facts.update(image=_file(workspace, path, "IMAGE"), take=take["id"], pose=pose_id)
    if kind == "concept-cell":
        sheet = concepts.load_sheet(workspace, params["sheet"])
        cell = concepts._cell(sheet, params["cell"])
        facts.update(sheet=sheet["id"], cell=cell, image=_file(workspace, concepts.sheet_dir(workspace, sheet["id"]) / cell["file"], "IMAGE"))
    if kind == "clip-take":
        take = load_take(workspace, "clip", params["clip"], params["take"])
        path = take_media_frames(workspace, take)
        facts.update(take={"id":take["id"],"media":take["media"]},
                     media=_images(workspace, path, "FRAMES",fps=take["media"]["fps"]) if isinstance(path,list) else _file(workspace, path, "VIDEO"))
    if kind == "prompt-template":
        snapshot = _render_prompt(workspace, params)
        facts["prompt"] = {key:value for key,value in snapshot.items() if key != "renderedAt"}
    if kind in {"image-edit", "concept-sheet", "video-from-frames"}:
        provider = params["provider"]
        adapter = get_provider(provider, tools) if kind == "video-from-frames" else get_image_provider(provider, tools)
        config = tools["providers"][provider]
        facts.update(provider=provider, model=adapter.model, settingsFingerprint=_hash({key:config.get(key) for key in ("model","size","audioOutput","command","baseUrl","site")}),
                     character={key: character.get(key) for key in ("basePose", "background")})
        if kind == "video-from-frames" and params["inputScale"] != 1:
            facts["character"]["canvas"] = character["canvas"]
        if kind != "video-from-frames":
            facts["baseTake"] = still_path(workspace, character["basePose"])[1]["id"]
    if kind in {"matte", "normalize", "interpolate", "external-processor", "save-pose-take"}:
        name = params.get("processor", "interpolate" if kind == "interpolate" else "alpha")
        if kind in {"matte","interpolate"} and not tools.get(name):
            raise ValueError(f"No '{name}' processor is configured in production/tools.json")
        facts["processorFingerprint"] = _hash(tools.get(name))
    if kind in {"matte","normalize","interpolate","reverse","pingpong","trim","scale","external-processor","load-video","save-clip-take"}:
        facts["ffmpeg"] = tools.get("ffmpeg")
    if kind in {"normalize", "still-qa", "save-pose-take"}:
        pose = load_owner(workspace, "pose", params["pose"])
        facts.update(character={key:character.get(key) for key in ("basePose","canvas","background","framing","anchors","tolerances")},
                     pose={"id":pose["id"],"expected":pose.get("expected")})
        base, take = still_path(workspace, character["basePose"])
        facts.update(base=_file(workspace, base, "IMAGE"), baseTake=take["id"])
    if kind == "save-clip-take":
        clip = load_owner(workspace, "clip", params["clip"])
        facts["clip"] = {key:clip.get(key) for key in ("id","from","to","kind","generation")}
    if kind.startswith("save-"):
        facts["owners"] = [{"kind":"pose","id":params["pose"]}] if kind == "save-pose-take" else \
            [{"kind":"clip","id":params["clip"]}] if kind == "save-clip-take" else [{"kind":"pose","id":pose} for pose in params["poses"]]
    if kind == "save-concept-sheet":
        concepts._poses(workspace,params["poses"],concepts.grid_spec(params["grid"]),create=False)
    known = {}
    if kind in {"base-still","approved-still"}:
        known["image"] = {"type":"IMAGE","sha256":facts["image"]["sha256"],"provenance":{**facts["image"]["provenance"],"pose":facts["pose"],"still":facts["take"]}}
        known["pose"] = {"type":"POSE","record":{"kind":"pose","owner":facts["pose"],"take":facts["take"]}}
    elif kind == "load-image":
        known["image"] = {"type":"IMAGE","provenance":facts["source"]["provenance"]}
    elif kind == "load-video":
        known["video"] = {"type":"VIDEO","provenance":facts["source"]["provenance"]}
    elif kind == "concept-cell":
        known["image"] = {"type":"IMAGE","provenance":{"conceptual":True,"concept":{"sheet":params["sheet"],"cell":params["cell"],"sha256":facts["image"]["sha256"]}}}
    elif kind == "clip-take":
        known["media"] = {"type":facts["media"]["type"],"provenance":{}}
        known["clip"] = {"type":"CLIP","record":{"kind":"clip","owner":params["clip"],"take":params["take"]}}
    elif kind in {"text","prompt-template"}:
        asset = _text(params["text"]) if kind == "text" else _text(snapshot["text"],snapshot=snapshot)
        asset.get("prompt",{}).pop("renderedAt",None)
        known["text"] = asset
        facts["prompt"] = _prompt(asset,require=False)
    elif kind == "join-text" and {"a","b"} <= inputs.keys():
        asset = _join(inputs["a"],inputs["b"],params["separator"])
        known["text"] = asset
        facts["prompt"] = _prompt(asset,require=False)
    elif kind == "reroute" and "input" in inputs:
        known["output"] = inputs["input"]
    elif kind in {"image-edit","concept-sheet","video-from-frames"}:
        if "prompt" in inputs and "text" in inputs["prompt"]:
            _prompt(inputs["prompt"])
        if kind != "video-from-frames" and "image" in inputs:
            _approved_base(workspace,inputs["image"])
        if kind == "video-from-frames":
            for role in ("first","last"):
                if role in inputs:
                    _approved_source(workspace,inputs[role])
        known["video" if kind == "video-from-frames" else "image"] = {"type":"VIDEO" if kind == "video-from-frames" else "IMAGE","provenance":{"conceptual":kind == "concept-sheet"}}
    elif kind == "split-grid" and "image" in inputs:
        known["images"] = {"type":"IMAGES","provenance":{**inputs["image"].get("provenance",{}),"conceptual":True}}
    elif kind == "select-image" and "images" in inputs:
        known["image"] = {"type":"IMAGE","provenance":inputs["images"].get("provenance",{})}
    elif kind == "still-qa" and "image" in inputs:
        known["image"] = inputs["image"]
    elif kind == "compare":
        known.update({role:inputs[role] for role in ("a","b") if role in inputs})
    elif kind == "save-pose-take":
        known["pose"] = {"type":"POSE","record":{"kind":"pose","owner":params["pose"]}}
    elif kind == "save-clip-take":
        known["clip"] = {"type":"CLIP","record":{"kind":"clip","owner":params["clip"]}}
    elif kind == "save-concept-sheet":
        known["images"] = {"type":"IMAGES","provenance":{"conceptual":True}}
    elif "media" in inputs:
        known["media"] = inputs["media"] if kind == "preview" else {"type":"FRAMES" if inputs["media"]["type"] == "VIDEO" else inputs["media"]["type"],"provenance":inputs["media"].get("provenance",{})}
    if kind == "save-pose-take" and inputs.get("image",{}).get("provenance",{}).get("conceptual"):
        raise ValueError("Concept images cannot be saved as pose takes; edit the approved base using them as references")
    if known:
        facts["outputs"] = known
    return facts


def _render_prompt(workspace: Path, params: dict) -> dict:
    library, character = prompts.load_library(workspace), load_character(workspace)
    template = params["template"]
    if template == "concept":
        return prompts.concept_prompt(library, character, [load_owner(workspace,"pose",pose) for pose in params["poses"]], concepts.grid_spec(params["grid"]))
    if template in {"still","still-reference"}:
        pose = load_owner(workspace,"pose",params["pose"])
        pose["prompt"] = {**pose["prompt"],"template":template}
        return prompts.pose_prompt(library,character,pose)
    clip = load_owner(workspace,"clip",params["clip"])
    clip["prompt"] = {**clip["prompt"],"template":template}
    return prompts.clip_prompt(library,character,clip)


def _asset(inputs: dict, name: str, accepted) -> dict:
    asset = inputs.get(name)
    types = [accepted] if isinstance(accepted, str) else accepted
    if not isinstance(asset, dict) or asset.get("type") not in types:
        raise ValueError(f"Input {name} needs {' / '.join(types)}")
    return asset


def _paths(workspace: Path, asset: dict) -> list[Path]:
    return [_path(workspace, value) for value in asset.get("paths", [asset.get("path")])]


def _approved_base(workspace: Path, asset: dict) -> None:
    _approved_source(workspace,asset,base=True)


def _approved_source(workspace: Path, asset: dict, *, base=False) -> None:
    """Approval is the current pose/take identity AND its canonical source bytes."""
    provenance = asset.get("provenance",{})
    pose = provenance.get("pose")
    if provenance.get("conceptual") or not pose or base and pose != load_character(workspace)["basePose"]:
        raise ValueError("Generation inputs must be canonical approved stills; concepts may only be image references")
    path,take = still_path(workspace,pose)
    canonical = hashlib.sha256(path.read_bytes()).hexdigest()
    if provenance.get("still") != take["id"] or asset.get("sha256") != canonical:
        raise ValueError("Generation input differs from the canonical approved still")
    if asset.get("path") and hashlib.sha256(_path(workspace,asset["path"]).read_bytes()).hexdigest() != canonical:
        raise ValueError("Generation input bytes changed since they were selected")


def _prompt(asset: dict, *, require: bool = True) -> dict:
    snapshot = deepcopy(asset.get("prompt") or {"text": asset["text"], "negative": "", "blocks": {},
        "complete": True, "placeholders": [], "sha256": asset["sha256"]})
    placeholders = [match.group(1) for match in prompts.PLACEHOLDER.finditer(snapshot["text"]+"\n"+snapshot.get("negative",""))]
    snapshot.update(complete=not placeholders,placeholders=placeholders)
    if require:
        prompts.require_complete(snapshot)
    return snapshot


def _workflow(record) -> dict:
    receipt = record({})
    return {**receipt["workflow"], "run": receipt["run"], "node": receipt["node"]}


def _origin(asset: dict, *, workflow=None) -> dict:
    provenance = asset.get("provenance") or {}
    source = deepcopy(provenance.get("provider") or {"provider": "workflow"})
    source["workflow"] = workflow
    if provenance.get("concept"):
        source["concept"] = deepcopy(provenance["concept"])
    return source


def _join(a: dict, b: dict, separator: str) -> dict:
    first, second = _prompt(a,require=False), _prompt(b,require=False)
    text = first["text"]+separator+second["text"]
    snapshot = {"text":text,"negative":separator.join(value for value in (first.get("negative",""),second.get("negative","")) if value),
                "blocks":{**first.get("blocks",{}),**second.get("blocks",{})},"parts":[first,second]}
    snapshot["sha256"] = _hash(snapshot)
    return _text(text,snapshot=snapshot)


def _provider_inputs(workspace: Path, node_dir: Path, images: dict[str,bytes], metadata: dict) -> dict:
    result = {}
    for role, data in images.items():
        path = node_dir / ("input.png" if role == "base" else f"{role}.png")
        write_durable(path,data)
        result[role] = {"path":path.relative_to(workspace.resolve()).as_posix(),"sha256":hashlib.sha256(data).hexdigest(),
                        **metadata.get(role,{})}
    return result


def _paid(workspace: Path, node_dir: Path, kind: str, params: dict, inputs: dict, record, log, previous=None) -> dict:
    from .clips import upload_image
    character, tools = load_character(workspace), load_tools(workspace)
    snapshot = _prompt(_asset(inputs,"prompt","TEXT"))
    name = params["provider"]
    video = kind == "video-from-frames"
    adapter = get_provider(name,tools) if video else get_image_provider(name,tools)
    images, input_facts = {}, {}
    if video:
        for role, port in (("first","first"),("last","last")):
            if port not in inputs:
                continue
            asset = _asset(inputs,port,"IMAGE")
            _approved_source(workspace,asset)
            images[role] = upload_image(character,read_bgra(_paths(workspace,asset)[0])[0],params["inputScale"])
            input_facts[role] = {"provenance":asset.get("provenance",{})}
        job = VideoJob(snapshot["text"],snapshot.get("negative","") if adapter.negative_prompt else "",images["first"],images.get("last"),params["durationS"],params["resolution"],params["seed"])
    else:
        asset = _asset(inputs,"image","IMAGE");_approved_base(workspace,asset)
        from .geometry import composite
        images["base"] = encode_png(composite(read_bgra(_paths(workspace,asset)[0])[0],character["background"]))
        input_facts["base"] = {"pose":character["basePose"],"still":still_path(workspace,character["basePose"])[1]["id"]}
        references = []
        if "reference" in inputs:
            reference = _asset(inputs,"reference","IMAGE")
            references = [_png_bytes(path) for path in _paths(workspace,reference)]
            if references and not adapter.supports_reference:
                raise ValueError("This image provider does not support references")
            if len(references) == 1:
                images["reference"] = references[0]
                input_facts["reference"] = deepcopy(reference.get("provenance",{}).get("concept") or {})
        grid = concepts.grid_spec(params["grid"]) if kind == "concept-sheet" else None
        size = (grid["cols"]*512,grid["rows"]*512) if grid else (params["width"],params["height"]) if params["width"] else None
        job = ImageJob(snapshot["text"],snapshot.get("negative","") if adapter.negative_prompt else "",images["base"],references,size)
    adapter.key()
    source_inputs = _provider_inputs(workspace,node_dir,images,input_facts)
    facts = {"state":"submitting","provider":name,"model":adapter.model,"request":adapter.preview(job),
             "prompt":{**snapshot,"negativeSent":bool(job.negative)},"inputs":source_inputs}
    if not video:
        facts["conceptual"] = kind == "concept-sheet"
        if "reference" in inputs and inputs["reference"].get("provenance",{}).get("concept"):
            facts["concept"] = deepcopy(inputs["reference"]["provenance"]["concept"])
    if previous:
        facts = {**deepcopy(previous),"state":"submitted"}
        record(facts)
    else:
        balance = adapter.balance() if video else None
        if balance is not None:
            facts["balanceBefore"] = balance
        record(facts)  # durable before the sole paid request
    try:
        if video:
            if not previous:
                facts.update(state="submitted",taskId=adapter.submit(job));record(facts)
            deadline = time.monotonic()+adapter.timeout_seconds
            while True:
                status,url,detail = adapter.poll(facts["taskId"])
                if status == "succeeded":
                    break
                if status == "failed":
                    facts.update(state="failed",error=detail);record(facts)
                    raise ValueError(f"Provider reported failure: {detail}")
                if time.monotonic() > deadline:
                    raise ValueError(f"Task {facts['taskId']} is still pending; resume this workflow to download it")
                log(detail or "pending");time.sleep(adapter.poll_seconds)
            target = node_dir/"output.mp4"
            adapter.fetch_result(facts["taskId"],url,target)
            metadata = video_info(target)
            balance = adapter.balance()
            if balance is not None:
                facts["balanceAfter"] = balance
            port,type_ = "video","VIDEO"
        else:
            data = adapter.edit(job)
            target = node_dir/("source"+image_suffix(data));write_durable(target,data)
            image = read_bgra(target)[0]
            metadata = {"width":image.shape[1],"height":image.shape[0]}
            port,type_ = "image","IMAGE"
        provenance = {"provider":{key:deepcopy(value) for key,value in facts.items() if key in {"provider","model","request","taskId","balanceBefore","balanceAfter"}},
                      "prompt":facts["prompt"],"inputs":facts["inputs"],"conceptual":kind == "concept-sheet"}
        if facts.get("concept"):
            provenance["concept"] = facts["concept"]
        provenance["workflowReceipt"] = _workflow(record)
        outputs = {port:_file(workspace,target,type_,provenance=provenance,**metadata)}
        record({**facts,"state":"ready","outputs":outputs})  # commits before any downstream save/QA
        return outputs
    except Exception as exc:
        facts.update(error=str(exc))
        if not video or not facts.get("taskId"):
            facts["state"] = "failed"
        record(facts)
        raise


def _png_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    return data if data.startswith(b"\x89PNG\r\n\x1a\n") else encode_png(read_bgra(path)[0])


def _local_media(workspace: Path, node_dir: Path, kind: str, params: dict, asset: dict) -> dict:
    from .stills import matte, normalize_image
    character, tools = load_character(workspace),load_tools(workspace)
    provenance = deepcopy(asset.get("provenance",{}))
    type_ = asset["type"]
    fps = asset.get("fps")
    paths = _paths(workspace,asset)
    if type_ == "VIDEO":
        fps = video_info(paths[0])["fps"]
        paths = media_frames(paths[0],tools.get("ffmpeg"),node_dir/"decoded")
        type_ = "FRAMES"
    if kind == "reverse":
        paths = paths[::-1]
    elif kind == "pingpong":
        paths = paths+paths[-2:0:-1]
    elif kind == "trim":
        start,end = params["start"], params["end"] or len(paths)
        if not 0 <= start < end <= len(paths):
            raise ValueError("Trim requires a non-empty range inside the frames")
        paths = paths[start:end]
    output = node_dir/"output"
    output.mkdir(exist_ok=True)
    normalization = None
    if kind in {"interpolate","external-processor"}:
        source = node_dir/"processor-input";source.mkdir(exist_ok=True)
        for index,path in enumerate(paths):
            write_png(source/f"{index:06d}.png",read_bgra(path)[0])
        name = "interpolate" if kind == "interpolate" else params["processor"]
        values = {"factor":params["factor"],"wrap":0} if kind == "interpolate" else {}
        run_processor(tools,name,source,output,**values)
        produced = sorted_pngs(output)
        expected = (len(paths)-1)*params["factor"]+1 if kind == "interpolate" else 1 if type_ == "IMAGE" else None
        if not produced or expected is not None and len(produced) != expected:
            raise ValueError("Processor returned an unexpected frame count")
        if kind == "interpolate":
            fps = float(fps)*params["factor"]
    elif kind in {"reverse","pingpong","trim"}:
        produced = []
        for index,path in enumerate(paths):
            target = output/f"{index:06d}.png";copy_durable(path,target);produced.append(target)
    else:
        produced = []
        for index,path in enumerate(paths):
            image,alpha = read_bgra(path)
            if kind == "matte":
                image = matte(tools,image,character["background"])
            elif kind == "normalize":
                pose = load_owner(workspace,"pose",params["pose"])
                place = (params["scale"],params["dx"],params["dy"]) if params["explicit"] else None
                image,normalization,_ = normalize_image(workspace,character,pose,image,alpha,place)
            elif kind == "scale":
                width,height = max(1,round(image.shape[1]*params["factor"])),max(1,round(image.shape[0]*params["factor"]))
                image = cv2.resize(image,(width,height),interpolation=cv2.INTER_AREA)
            target = output/f"{index:06d}.png";write_png(target,image);produced.append(target)
    if type_ == "IMAGE":
        return _file(workspace,produced[0],"IMAGE",provenance=provenance,**({"normalization":normalization} if normalization else {}))
    return _images(workspace,produced,"FRAMES",provenance=provenance,fps=fps)


def execute(workspace: Path, node_dir: Path, kind: str, params: dict, inputs: dict, *, record, log, previous=None) -> dict:
    """Execute one allowlisted operation. Paid requests are never retried here."""
    workspace,node_dir = workspace.resolve(),node_dir.resolve()
    node_dir.relative_to(workspace)  # write authority belongs to the selected workspace
    params = validate_params(workspace,kind,params)
    node_dir.mkdir(parents=True,exist_ok=True)
    character = load_character(workspace)
    if kind in {"base-still","approved-still"}:
        pose_id = params.get("pose",character["basePose"])
        path,take = still_path(workspace,pose_id)
        provenance = {"pose":pose_id,"still":take["id"]}
        return {"image":_file(workspace,path,"IMAGE",provenance=provenance),"pose":_record_asset("POSE",load_owner(workspace,"pose",pose_id),take=take)}
    if kind == "concept-cell":
        sheet = concepts.load_sheet(workspace,params["sheet"]);cell = concepts._cell(sheet,params["cell"])
        path = concepts.sheet_dir(workspace,sheet["id"])/cell["file"]
        asset = _file(workspace,path,"IMAGE",provenance={"conceptual":True})
        asset["provenance"]["concept"] = {"sheet":sheet["id"],"cell":cell["index"],"sha256":asset["sha256"]}
        return {"image":asset}
    if kind == "clip-take":
        owner = load_owner(workspace,"clip",params["clip"]);take = load_take(workspace,"clip",params["clip"],params["take"])
        path = take_media_frames(workspace,take)
        provenance = {"clip":owner["id"],"take":take["id"]}
        media = _images(workspace,path,"FRAMES",provenance=provenance,fps=take["media"]["fps"]) if isinstance(path,list) else _file(workspace,path,"VIDEO",provenance=provenance,**{key:value for key,value in take["media"].items() if key != "video"})
        return {"media":media,"clip":_record_asset("CLIP",owner,take=take)}
    if kind in {"load-image","load-video"}:
        path = _path(workspace,params["path"])
        return {"image":_file(workspace,path,"IMAGE")} if kind == "load-image" else {"video":_file(workspace,path,"VIDEO",**video_info(path))}
    if kind == "text":
        return {"text":_text(params["text"])}
    if kind == "prompt-template":
        snapshot = _render_prompt(workspace,params);return {"text":_text(snapshot["text"],snapshot=snapshot)}
    if kind == "join-text":
        return {"text":_join(_asset(inputs,"a","TEXT"),_asset(inputs,"b","TEXT"),params["separator"])}
    if kind == "reroute":
        return {"output":deepcopy(_asset(inputs,"input",params["type"]))}
    if kind in {"image-edit","concept-sheet","video-from-frames"}:
        return _paid(workspace,node_dir,kind,params,inputs,record,log,previous)
    if kind == "split-grid":
        asset = _asset(inputs,"image","IMAGE");provenance = {**deepcopy(asset.get("provenance",{})),"conceptual":True}
        paths = []
        for index,image in enumerate(concepts.split_grid(read_bgra(_paths(workspace,asset)[0])[0],concepts.grid_spec(params["grid"]))):
            path = node_dir/f"{index:06d}.png";write_png(path,image);paths.append(path)
        return {"images":_images(workspace,paths,"IMAGES",provenance=provenance)}
    if kind == "select-image":
        asset = _asset(inputs,"images",["IMAGES","FRAMES"]);paths = _paths(workspace,asset)
        if params["index"] >= len(paths):
            raise ValueError("Selected image is outside the list")
        result = _file(workspace,paths[params["index"]],"IMAGE",provenance=asset.get("provenance",{}))
        if asset.get("cells"):
            result["provenance"]["concept"] = deepcopy(asset["cells"][params["index"]])
        return {"image":result}
    if kind in {"matte","normalize","interpolate","reverse","pingpong","trim","scale","external-processor"}:
        return {"media":_local_media(workspace,node_dir,kind,params,_asset(inputs,"media",REGISTRY[kind]["inputs"]["media"]["type"]))}
    if kind == "preview":
        return {"media":deepcopy(_asset(inputs,"media",REGISTRY[kind]["inputs"]["media"]["type"]))}
    if kind == "still-qa":
        from .stills import qa_for
        asset = _asset(inputs,"image","IMAGE")
        qa = qa_for(character,load_owner(workspace,"pose",params["pose"]),read_bgra(_paths(workspace,asset)[0])[0],asset.get("normalization"))
        return {"image":deepcopy(asset),"qa":_text(json.dumps(qa,ensure_ascii=False,sort_keys=True))}
    if kind == "compare":
        a,b = _asset(inputs,"a","IMAGE"),_asset(inputs,"b","IMAGE")
        first,second = read_bgra(_paths(workspace,a)[0])[0],read_bgra(_paths(workspace,b)[0])[0]
        same_size = first.shape == second.shape
        report = {"sameSize":same_size,"aSize":list(first.shape[1::-1]),"bSize":list(second.shape[1::-1]),
                  "identicalPixels":same_size and bool((first == second).all())}
        return {"a":deepcopy(a),"b":deepcopy(b),"report":_text(json.dumps(report,sort_keys=True))}
    workflow = _workflow(record)
    if kind == "save-pose-take":
        from .stills import import_still
        asset = _asset(inputs,"image","IMAGE")
        if asset.get("provenance",{}).get("conceptual"):
            raise ValueError("Concept images cannot be saved as pose takes")
        origin = asset.get("provenance",{})
        take = import_still(workspace,params["pose"],_paths(workspace,asset)[0],note=params["note"],
                            place=(1.0,0.0,0.0) if asset.get("normalization") else None,
                            source_facts=_origin(asset,workflow=workflow),prompt_snapshot=origin.get("prompt"),source_inputs=origin.get("inputs"))
        if take["state"] != "ready":
            raise ValueError(take.get("error") or "Pose import did not produce a ready candidate")
        return {"pose":_record_asset("POSE",load_owner(workspace,"pose",params["pose"]),take=take,provenance={"workflow":workflow})}
    if kind == "save-clip-take":
        from .clips import import_clip_take
        asset = _asset(inputs,"media",["VIDEO","FRAMES"]);paths = _paths(workspace,asset)
        if asset["type"] == "FRAMES":
            target = node_dir/"take-frames";target.mkdir(exist_ok=True)
            for index,path in enumerate(paths):copy_durable(path,target/f"{index:06d}.png")
        else:target = paths[0]
        origin = asset.get("provenance",{})
        take = import_clip_take(workspace,params["clip"],target,fps=asset.get("fps"),note=params["note"],
                                source_facts=_origin(asset,workflow=workflow),prompt_snapshot=origin.get("prompt"),source_inputs=origin.get("inputs"))
        if take["state"] != "ready":
            raise ValueError(take.get("error") or "Clip import did not produce a ready candidate")
        return {"clip":_record_asset("CLIP",load_owner(workspace,"clip",params["clip"]),take=take,provenance={"workflow":workflow})}
    if kind == "save-concept-sheet":
        asset = _asset(inputs,"image","IMAGE");origin = asset.get("provenance",{})
        sheet = concepts.import_sheet(workspace,_paths(workspace,asset)[0],params["poses"],params["grid"],source_facts=_origin(asset,workflow=workflow),
                                      prompt_snapshot=origin.get("prompt"),source_inputs=origin.get("inputs"))
        paths = [concepts.sheet_dir(workspace,sheet["id"])/cell["file"] for cell in sheet["cells"]]
        output = _images(workspace,paths,"IMAGES",provenance={"conceptual":True,"workflow":workflow})
        output["cells"] = [{"sheet":sheet["id"],"cell":index,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()} for index,path in enumerate(paths)]
        return {"images":output}
    raise ValueError(f"Unknown workflow operation: {kind}")

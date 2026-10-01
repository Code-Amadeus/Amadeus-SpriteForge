"""`spriteforge production ...` commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _owner(parser: argparse.ArgumentParser, clip_only: bool = False) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    if not clip_only:
        group.add_argument("--pose", help="Pose id (still takes)")
    group.add_argument("--clip", help="Clip id (video takes)")


def add_parser(commands) -> None:
    production = commands.add_parser("production", help="Pose stills, video takes, rendering and production QA")
    sub = production.add_subparsers(dest="action", required=True)

    def command(name: str, help_text: str) -> argparse.ArgumentParser:
        parser = sub.add_parser(name, help=help_text)
        parser.add_argument("--workspace", type=Path, required=True)
        return parser

    init = command("init", "Create the production character, prompt library and tool settings")
    init.add_argument("--id", required=True)
    init.add_argument("--display-name", required=True)
    init.add_argument("--canvas", required=True, help="WIDTHxHEIGHT of every runtime frame, e.g. 764x1028")
    init.add_argument("--base-pose", default="idle")
    init.add_argument("--background", default="255,255,255", help="R,G,B used to flatten stills for providers")
    init.add_argument("--cut-edges", default="bottom", help="Comma list of canvas edges the body may cross")
    status = command("status", "Summarise poses, clips, takes and renders")
    status.add_argument("--json", action="store_true")
    settings = command("settings", "Show or change Studio's image provider and batch confirmation defaults")
    settings.add_argument("--concept-provider")
    settings.add_argument("--still-provider")
    settings.add_argument("--batch-confirm-threshold", type=int)
    known = command("review-known", "Annotate a current watch issue, or clear its annotation")
    known.add_argument("key")
    annotation = known.add_mutually_exclusive_group(required=True)
    annotation.add_argument("--note")
    annotation.add_argument("--clear", action="store_true")
    behavior = sub.add_parser("behavior", help="Read graph statistics and deterministic trigger simulations").add_subparsers(
        dest="behavior_action", required=True)
    for name in ("stats", "trigger-test"):
        step = behavior.add_parser(name)
        step.add_argument("--workspace", type=Path, required=True)
        step.add_argument("--minutes", type=int, default=10, choices=(10, 30, 60))
        step.add_argument("--seed", type=int, default=1)
        if name == "trigger-test":
            step.add_argument("--events", type=Path, required=True, help="JSON list of {atS,label} or {atS,speech:true}")
    release = command("export", "Export a versioned runtime pack and record its source hashes and notes")
    release.add_argument("--version", required=True)
    release.add_argument("--notes", default="")

    concept = sub.add_parser("concept", help="Generate, import, pick and reroll expression reference sheets").add_subparsers(
        dest="concept_action", required=True)
    for name in ("new", "import", "pick", "reroll"):
        step = concept.add_parser(name)
        step.add_argument("--workspace", type=Path, required=True)
        if name in {"new", "import"}:
            step.add_argument("--poses", required=True, help="Comma-separated unique pose ids, at most one per cell")
            step.add_argument("--grid", default="3x2", help="3x2 (default) or 2x2")
        if name == "import":
            step.add_argument("file", type=Path)
        if name in {"pick", "reroll"}:
            step.add_argument("sheet")
            step.add_argument("cell", type=int, help="Zero-based row-major cell index")
        if name == "pick":
            step.add_argument("--pose")
            step.add_argument("--unpick", action="store_true")
        if name in {"new", "reroll"}:
            step.add_argument("--provider", required=True)
            step.add_argument("--dry-run", action="store_true")

    pose = sub.add_parser("pose", help="Plan poses").add_subparsers(dest="pose_action", required=True)
    pose_add = pose.add_parser("add")
    pose_add.add_argument("--workspace", type=Path, required=True)
    pose_add.add_argument("id")
    pose_add.add_argument("--description", default="")
    expect = pose.add_parser("expect", help="Record an intended head offset for a pose (e.g. a side turn)")
    expect.add_argument("--workspace", type=Path, required=True)
    expect.add_argument("id")
    expect.add_argument("--head-top", type=float)
    expect.add_argument("--head-center", type=float)

    clip = sub.add_parser("clip", help="Plan clips").add_subparsers(dest="clip_action", required=True)
    clip_add = clip.add_parser("add")
    clip_add.add_argument("--workspace", type=Path, required=True)
    clip_add.add_argument("id")
    clip_add.add_argument("--from", dest="source", required=True)
    clip_add.add_argument("--to", dest="target", required=True)
    clip_add.add_argument("--phase", choices=["in", "loop", "out"])
    variant = clip.add_parser("variant", help="Create a sibling clip with copied settings and a new subject block")
    variant.add_argument("--workspace", type=Path, required=True)
    variant.add_argument("source")
    variant.add_argument("id")
    clip_plan = clip.add_parser("plan", help="Create only the clip records in a JSON plan for approved stills")
    clip_plan.add_argument("--workspace", type=Path, required=True)
    clip_plan.add_argument("--file", type=Path, required=True, help="JSON list of {id,from,to,phase?}")
    clip_set = clip.add_parser("set", help="Change generation, processing or playback settings")
    clip_set.add_argument("--workspace", type=Path, required=True)
    clip_set.add_argument("id")
    clip_set.add_argument("--provider")
    clip_set.add_argument("--duration", type=int, help="Seconds requested from the provider")
    clip_set.add_argument("--resolution")
    clip_set.add_argument("--seed", type=int)
    clip_set.add_argument("--input-scale", type=float, help="Shrink the subject inside provider inputs (0.5-1)")
    clip_set.add_argument("--last-frame", choices=["still", "none"],
                          help="Transitions: send the end pose still, or generate from the first frame only")
    clip_set.add_argument("--register", action=argparse.BooleanOptionalAction,
                          help="Register both ends to the pose stills (off: frames are already on the canvas)")
    clip_set.add_argument("--margin", type=int, help="Transparent columns added on each side of the canvas")
    clip_set.add_argument("--interpolate", type=int, help="Frame multiplier from the interpolate processor")
    clip_set.add_argument("--pingpong", action=argparse.BooleanOptionalAction)
    clip_set.add_argument("--lock-head", type=int, help="Frames blended into the start still")
    clip_set.add_argument("--lock-tail", type=int, help="Frames blended into the end still")
    clip_set.add_argument("--edge-guard", type=int, help="Clear alpha this many px from closed canvas edges")
    clip_set.add_argument("--speed", type=float, help="Playback speed multiplier")
    clip_set.add_argument("--loop-mode", choices=["loop", "once_then_hold"])
    clip_set.add_argument("--mouth", help="Mouth set for silence overlays on this speaking loop, or 'off'")
    clip_set.add_argument("--mouth-source", help="Closed-mouth image: shared (default), still, frame:N or pose:ID")

    mouth = sub.add_parser("mouth", help="Mouth sets and closed-mouth sources").add_subparsers(dest="mouth_action", required=True)
    mouth_set = mouth.add_parser("set", help="Create or change a mouth set (canvas-centre pixels)")
    mouth_set.add_argument("--workspace", type=Path, required=True)
    mouth_set.add_argument("name")
    for field in ("cx", "cy", "width", "height", "curve"):
        mouth_set.add_argument(f"--{field}", type=float)
    shared = mouth.add_parser("shared", help="Pose whose still is the shared closed mouth (default: the base pose)")
    shared.add_argument("--workspace", type=Path, required=True)
    shared.add_argument("pose", help="Pose id, or 'default'")
    per_pose = mouth.add_parser("pose", help="Closed-mouth pose for one pose's speaking loops (e.g. a side view)")
    per_pose.add_argument("--workspace", type=Path, required=True)
    per_pose.add_argument("pose")
    per_pose.add_argument("--use", required=True, help="Pose whose still is the closed mouth, or 'default'")

    prompt = sub.add_parser("prompt", help="Versioned prompt blocks").add_subparsers(dest="prompt_action", required=True)
    show = prompt.add_parser("show")
    show.add_argument("--workspace", type=Path, required=True)
    show.add_argument("block", nargs="?")
    set_block = prompt.add_parser("set", help="Add a version to a prompt block")
    set_block.add_argument("--workspace", type=Path, required=True)
    set_block.add_argument("block")
    text = set_block.add_mutually_exclusive_group(required=True)
    text.add_argument("--text")
    text.add_argument("--file", type=Path)
    set_block.add_argument("--description")
    render_prompt = prompt.add_parser("render", help="Show the prompt a pose or clip would use now")
    render_prompt.add_argument("--workspace", type=Path, required=True)
    _owner(render_prompt)
    set_template = prompt.add_parser("template", help="Create or replace a template (the order of its blocks)")
    set_template.add_argument("--workspace", type=Path, required=True)
    set_template.add_argument("template", help="Template id; clips use 'transition' or 'loop', poses 'still'")
    set_template.add_argument("--blocks", required=True, help="Comma list of block ids; @subject is the clip's or pose's own block")
    set_template.add_argument("--negative", default="", help="Comma list of negative-prompt block ids")
    set_template.add_argument("--join", help="Text between blocks (default: a blank line); '，' makes one sentence")
    export = prompt.add_parser("export", help="Write templates and their shared blocks to a preset file")
    export.add_argument("--workspace", type=Path, required=True)
    export.add_argument("file", type=Path)
    export.add_argument("--template", action="append", help="Template to include (default: all)")
    imp_preset = prompt.add_parser("import", help="Add a preset's block texts as new versions and install its templates")
    imp_preset.add_argument("--workspace", type=Path, required=True)
    imp_preset.add_argument("file", type=Path)

    prepare = command("prepare", "Write the exact inputs and prompt for an external generator")
    _owner(prepare)
    prepare.add_argument("--output", type=Path, required=True)

    take = sub.add_parser("take", help="Import, review and resume takes").add_subparsers(dest="take_action", required=True)
    imp = take.add_parser("import", help="Import a still image (pose) or a video/frame folder (clip)")
    imp.add_argument("--workspace", type=Path, required=True)
    _owner(imp)
    imp.add_argument("path", type=Path)
    imp.add_argument("--fps", type=float, help="Frame rate of a frame-folder clip import")
    imp.add_argument("--note", default="")
    imp.add_argument("--place", help="SCALE,DX,DY placing a still on the canvas instead of automatic placement")
    note = take.add_parser("note", help="Change an annotation without changing a take's source or snapshots")
    note.add_argument("--workspace", type=Path, required=True)
    _owner(note)
    note.add_argument("take")
    note.add_argument("--note", required=True)
    for name in ("accept", "reject", "restore"):
        decision = take.add_parser(name)
        decision.add_argument("--workspace", type=Path, required=True)
        _owner(decision)
        decision.add_argument("take")
        decision.add_argument("--reason", default="")
    adopt = take.add_parser("adopt", help="Make a pose still from one frame of a clip take")
    adopt.add_argument("--workspace", type=Path, required=True)
    adopt.add_argument("--clip", required=True)
    adopt.add_argument("take")
    adopt.add_argument("--pose", help="Pose that receives the still (default: the clip's end pose)")
    adopt.add_argument("--frame", default="last", help="'last' (default), 'first' or a 0-based frame index of the take")
    adopt.add_argument("--note", default="")
    resume = take.add_parser("resume", help="Continue polling a submitted provider task")
    resume.add_argument("--workspace", type=Path, required=True)
    _owner(resume, clip_only=True)
    resume.add_argument("take")
    for name, text in (("process", "Process and QA a candidate without replacing published clip output"),
                       ("adopt-processed", "Publish a current processed candidate whose QA has no failure")):
        step = take.add_parser(name, help=text)
        step.add_argument("--workspace", type=Path, required=True)
        _owner(step, clip_only=True)
        step.add_argument("take")

    generate = command("generate", "Edit the base still into a pose, or submit a clip to its image-to-video provider")
    _owner(generate)
    generate.add_argument("--provider", help="Image-edit provider for a pose (required); overrides a clip's video provider")
    generate.add_argument("--dry-run", action="store_true", help="Print the request without sending it")
    generate.add_argument("--no-wait", action="store_true", help="Clips: return after submission; resume later")
    generate.add_argument("--based-on", help="Clip take whose version this generation is based on")
    generate.add_argument("--note", default="", help="Clip version annotation")
    generate.add_argument("--concept", help="Pose generation: expression reference SHEET:CELL")
    render = command("render", "Render accepted takes into graph-bindable frames")
    target = render.add_mutually_exclusive_group(required=True)
    target.add_argument("--clip")
    target.add_argument("--stale", action="store_true", help="Every clip whose render is missing or stale")
    render.add_argument("--keep-work", action="store_true")
    qa = command("qa", "Check graph seams and production-bound nodes")
    qa.add_argument("--output", type=Path)
    runtime = command("runtime-clips", "Clips exported by label without a graph node (show, set or clear)")
    runtime.add_argument("clips", nargs="*")
    runtime.add_argument("--clear", action="store_true")
    legacy = sub.add_parser("import-legacy", help="Import a character made with the earlier tools")
    steps = legacy.add_subparsers(dest="import_action", required=True)
    plan = steps.add_parser("plan", help="Read a legacy workspace and the pack it shipped; write a plan to review")
    plan.add_argument("--legacy", type=Path, required=True, help="Legacy SpriteForge workspace (read only)")
    plan.add_argument("--pack", type=Path, required=True, help="Shipped character pack (read only)")
    plan.add_argument("--output", type=Path, required=True, help="Plan file to write")
    apply = steps.add_parser("apply", help="Build the production character from a plan; safe to run again")
    apply.add_argument("--workspace", type=Path, required=True)
    apply.add_argument("plan", type=Path)
    sync = command("graph-sync", "Copy render timing onto bound graph nodes")
    sync.add_argument("--add-missing", action="store_true", help="Add a node for each rendered clip not in the graph")


def _print_status(state: dict) -> None:
    character = state["character"]
    anchors = character.get("anchors")
    print(f"{character['displayName']} ({character['id']}): canvas {character['canvas']['width']}x"
          f"{character['canvas']['height']}, base pose {character['basePose']}, "
          + (f"head top {anchors['headTopY']}, head centre {anchors['headCenterX']}" if anchors else "no approved base still"))
    tools = state["tools"]
    print("tools: " + ", ".join(f"{k}={'yes' if tools[k] else 'no'}" for k in ("ffmpeg", "alpha", "interpolate"))
          + "; providers: " + ", ".join(f"{n} key={'set' if p['keySet'] else 'missing'}" for n, p in tools["providers"].items()))
    for pose in state["poses"]:
        counts = {}
        for take in pose["takes"]:
            counts[take["status"]] = counts.get(take["status"], 0) + 1
        print(f"pose {pose['id']:24s} accepted={pose['acceptedTake'] or '-'} takes={counts or {}}"
              + (" RECHECK: base anchors changed" if pose["needsRecheck"] else ""))
    for clip in state["clips"]:
        counts = {}
        for take in clip["takes"]:
            counts[take["status"]] = counts.get(take["status"], 0) + 1
        render = clip["render"]
        qa = (render.get("qa") or {}).get("status", "-")
        print(f"clip {clip['id']:24s} {clip['from']}->{clip['to']} ({clip['kind']}) accepted={clip['acceptedTake'] or '-'} "
              f"takes={counts or {}} render={render['state']} qa={qa}"
              + (f" ({'; '.join(render['reasons'])})" if render["state"] == "stale" else ""))


def run(args) -> None:
    from . import project, prompts
    from .records import load_character
    action = args.action
    if action == "import-legacy":
        _run_import(args)
        return
    workspace = args.workspace.resolve()
    if action == "init":
        width, height = (int(v) for v in args.canvas.lower().split("x"))
        character = project.init_production(
            workspace, character_id=args.id, display_name=args.display_name, width=width, height=height,
            base_pose=args.base_pose, background=[int(v) for v in args.background.split(",")],
            cut_edges=[e.strip() for e in args.cut_edges.split(",") if e.strip()])
        print(f"Production character {character['id']} ready; import the base still with "
              f"'production take import --pose {character['basePose']} IMAGE'")
    elif action == "status":
        state = project.overview(workspace)
        if args.json:
            print(json.dumps(state, ensure_ascii=False, indent=2))
        else:
            _print_status(state)
    elif action == "settings":
        from .tools import set_ui_defaults
        values = {key: value for key, value in {
            "conceptProvider": args.concept_provider, "stillProvider": args.still_provider,
            "batchConfirmThreshold": args.batch_confirm_threshold,
        }.items() if value is not None}
        print(json.dumps(set_ui_defaults(workspace, values), ensure_ascii=False, indent=2))
    elif action == "review-known":
        from .issues import set_known
        print(json.dumps(set_known(workspace, args.key, args.note or "", clear=args.clear), ensure_ascii=False, indent=2))
    elif action == "behavior":
        from .api import ProductionApi
        api = ProductionApi(workspace)
        result = api.behavior_stats(args.minutes, args.seed) if args.behavior_action == "stats" else api.behavior_trigger_test(
            args.minutes, args.seed, json.loads(args.events.read_text(encoding="utf-8")))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif action == "export":
        from .exports import export_workspace
        print(json.dumps(export_workspace(workspace, args.version, notes=args.notes), ensure_ascii=False, indent=2))
    elif action == "concept":
        from .concepts import generate_sheet, import_sheet, reroll_cell, set_cell
        if args.concept_action == "new":
            result = generate_sheet(workspace, _ids(args.poses), args.grid, args.provider, dry_run=args.dry_run)
        elif args.concept_action == "import":
            result = import_sheet(workspace, args.file.resolve(), _ids(args.poses), args.grid)
        elif args.concept_action == "pick":
            result = set_cell(workspace, args.sheet, args.cell, picked=not args.unpick, pose=args.pose)
        else:
            result = reroll_cell(workspace, args.sheet, args.cell, args.provider, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif action == "pose":
        if args.pose_action == "add":
            project.add_pose(workspace, args.id, args.description)
            print(f"Pose {args.id} added")
        else:
            from .stills import set_expected
            pose = set_expected(workspace, args.id, args.head_top, args.head_center)
            print(f"Pose {args.id} expected anchors: {pose['expected'] or 'base anchors'}")
    elif action == "clip":
        if args.clip_action == "add":
            clip = project.add_clip(workspace, args.id, args.source, args.target, args.phase)
            print(f"Clip {clip['id']}: {clip['from']} -> {clip['to']} ({clip['kind']}, phase {clip['phase']})")
        elif args.clip_action == "variant":
            clip = project.add_variant(workspace, args.source, args.id)
            print(f"Variant {clip['id']} created from {args.source}; no takes copied")
        elif args.clip_action == "plan":
            from ..workspace import read_json
            entries = read_json(args.file)
            clips = project.plan_clips(workspace, entries.get("clips") if isinstance(entries, dict) else entries)
            print("Planned clips: " + ", ".join(clip["id"] for clip in clips))
        else:
            changes = {k: getattr(args, k) for k in project.CLIP_SETTINGS}
            clip = project.set_clip(workspace, args.id, mouth=args.mouth, mouth_source=args.mouth_source, **changes)
            print(json.dumps({k: clip.get(k) for k in ("generation", "processing", "playback", "mouth")}, indent=2))
    elif action == "mouth":
        if args.mouth_action == "set":
            values = project.set_mouth_set(workspace, args.name, **{k: getattr(args, k) for k in ("cx", "cy", "width", "height", "curve")})
            print(f"Mouth set {args.name}: {values}")
        else:
            shared = args.mouth_action == "shared"
            requested = args.pose if shared else args.use
            source = None if requested == "default" else requested
            project.set_closed_mouth(workspace, source, pose_id=None if shared else args.pose)
            print(f"Closed mouth for {'the character' if shared else 'pose ' + args.pose}: {source or 'default'}")
    elif action == "prompt":
        if args.prompt_action == "show":
            library = prompts.load_library(workspace)
            blocks = [args.block] if args.block else sorted(library["blocks"])
            for block_id in blocks:
                version = prompts.current(library, block_id)
                print(f"[{block_id}] v{version['version']}: {version['text']}")
        elif args.prompt_action == "set":
            library = prompts.load_library(workspace)
            text = args.text if args.text is not None else args.file.read_text(encoding="utf-8")
            version = prompts.set_block(library, args.block, text, args.description)
            prompts.save_library(workspace, library)
            print(f"{args.block} is at version {version}")
        elif args.prompt_action == "template":
            library = prompts.load_library(workspace)
            template = prompts.set_template(library, args.template, _ids(args.blocks), _ids(args.negative), args.join)
            prompts.save_library(workspace, library)
            print(f"Template {args.template}: {' + '.join(template['blocks'])}")
        elif args.prompt_action == "export":
            from ..workspace import atomic_json
            preset = prompts.export_preset(prompts.load_library(workspace), args.template)
            atomic_json(args.file, preset)
            print(f"Wrote {len(preset['templates'])} template(s) and {len(preset['blocks'])} block(s) to {args.file}")
        elif args.prompt_action == "import":
            from ..workspace import read_json
            library = prompts.load_library(workspace)
            versions = prompts.import_preset(library, read_json(args.file))
            prompts.save_library(workspace, library)
            print("Blocks: " + ", ".join(f"{block} v{version}" for block, version in versions.items()))
        else:
            rendered = _render_for(workspace, args)
            print(rendered["text"] + ("\n\nNEGATIVE:\n" + rendered["negative"] if rendered["negative"] else ""))
            print(f"\nblocks={rendered['blocks']} complete={rendered['complete']}")
    elif action == "prepare":
        from .clips import prepare
        kind, owner = ("pose", args.pose) if args.pose else ("clip", args.clip)
        paths = prepare(workspace, kind, owner, args.output.resolve())
        for path in paths:
            print(path)
        if kind == "clip" and "last.png" not in {p.name for p in paths}:
            print("No last frame: generate from first.png alone, then adopt a frame of the result as the end pose still")
    elif action == "take":
        _run_take(workspace, args)
    elif action == "generate" and args.pose:
        from .providers import IMAGE_PROVIDERS
        from .stills import generate_still
        if args.based_on is not None or args.note:
            raise ValueError("--based-on and --note only apply to clip generation")
        if not args.provider:
            raise ValueError(f"Choose an image-edit provider with --provider: {', '.join(IMAGE_PROVIDERS)}")
        concept = None
        if args.concept:
            sheet, separator, cell = args.concept.partition(":")
            if not separator or not cell.isdigit():
                raise ValueError("--concept needs SHEET:CELL")
            concept = {"sheet": sheet, "cell": int(cell)}
        result = generate_still(workspace, args.pose, args.provider, dry_run=args.dry_run, concept=concept)
        if args.dry_run:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            _print_still_qa(result)
    elif action == "generate":
        from .clips import generate_clip_take
        if args.concept:
            raise ValueError("--concept only applies to pose generation")
        result = generate_clip_take(workspace, args.clip, provider=args.provider, wait=not args.no_wait,
                                    dry_run=args.dry_run, based_on=args.based_on, note=args.note)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.dry_run else f"Take {result['id']}: {result['state']}")
    elif action == "render":
        from .records import list_owners, render_freshness
        from .render import render_clip
        targets = [args.clip] if args.clip else [c["id"] for c in list_owners(workspace, "clip")
                                                 if c.get("acceptedTake") and render_freshness(workspace, c)[0] != "current"]
        for clip_id in targets:
            render_clip(workspace, clip_id, keep_work=args.keep_work)
        if not targets:
            print("Every accepted clip is rendered and current")
    elif action == "qa":
        from ..workspace import atomic_json, read_json, resolve_asset
        from .checks import graph_report
        report = graph_report(workspace, read_json(resolve_asset(workspace, "graph_config.json")), load_character(workspace))
        if args.output:
            atomic_json(args.output, report)
        for node in report["nodes"]:
            print(f"node {node['label']:24s} {node['level']:5s} {'; '.join(node['issues'])}")
        for edge in report["edges"]:
            print(f"edge {edge['from']} -> {edge['to']}: {edge['level']} faceL={edge['faceL']} "
                  f"dHeadTop={edge['dHeadTop']} dHeadCenter={edge['dHeadCenter']}")
        print(f"QA: {report['status']}")
    elif action == "runtime-clips":
        if args.clips or args.clear:
            project.set_runtime_clips(workspace, [] if args.clear else args.clips)
        print("Runtime clips: " + (", ".join(load_character(workspace).get("runtimeClips") or []) or "none"))
    elif action == "graph-sync":
        result = project.graph_sync(workspace, add_missing=args.add_missing)
        for line in result["changes"]:
            print("updated " + line)
        for clip_id in result["added"]:
            print("added node " + clip_id)
        for clip_id in result["notRendered"]:
            print(f"not rendered: {clip_id}")
        if not any(result.values()):
            print("Graph already matches the rendered clips")


def _run_import(args) -> None:
    from ..workspace import atomic_json, read_json
    from .legacy import apply_import, plan_import
    if args.import_action == "plan":
        plan = plan_import(args.legacy, args.pack)
        atomic_json(args.output, plan)
        for pose_id, pose in plan["poses"].items():
            print(f"pose {pose_id:16s} still {pose['still']['clip']}:{pose['still']['end']} "
                  f"head {pose['anchors']['headTopY']},{pose['anchors']['headCenterX']} ({len(pose['members'])} endpoints)")
        for label, clip in plan["clips"].items():
            extra = [f"pad top {clip['padTop']}" if clip.get("padTop") else "", f"margin {clip['marginPx']}" if clip.get("marginPx") else "",
                     f"mouth {clip['mouth']['set']} {clip['mouth']['closedSource']}" if clip.get("mouth") else ""]
            print(f"clip {label:24s} {clip.get('from', '?')} -> {clip.get('to', '?')} {clip['frames']} frames "
                  f"@ {clip['frameIntervalMs']} ms {' '.join(e for e in extra if e)}")
        for note in plan["notes"]:
            print("NOTE: " + note)
        print(f"Plan written to {args.output}; review it, then run 'production import-legacy apply'")
        return
    report = apply_import(args.workspace.resolve(), read_json(args.plan))
    for node in report["nodes"]:
        if node["issues"]:
            print(f"node {node['label']}: {'; '.join(node['issues'])}")
    labels = {node["node"]: node["label"] for node in report["nodes"]}
    for edge in report["edges"]:
        if edge["level"] != "pass":
            print(f"edge {labels.get(edge['from'], edge['from'])} -> {labels.get(edge['to'], edge['to'])}: {edge['level']} "
                  f"faceL={edge['faceL']} dHeadTop={edge['dHeadTop']} dHeadCenter={edge['dHeadCenter']}")
    print(f"Imported; graph QA {report['status']}")


def _ids(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _render_for(workspace: Path, args) -> dict:
    from .clips import clip_prompt
    from .records import load_character, load_owner
    from .stills import still_prompt
    character = load_character(workspace)
    if args.pose:
        return still_prompt(workspace, character, load_owner(workspace, "pose", args.pose))
    return clip_prompt(workspace, character, load_owner(workspace, "clip", args.clip))


def _print_still_qa(take: dict) -> None:
    print(f"Still take {take['id']}: {take['normalization']['method']}, QA {take['qa']['status']}")
    for check in take["qa"]["checks"]:
        print(f"  {check['level']}: {check['message']}")


def _run_take(workspace: Path, args) -> None:
    from .records import decide
    if args.take_action == "adopt":
        from .stills import adopt_frame
        take = adopt_frame(workspace, args.clip, args.take, pose_id=args.pose, frame=args.frame, note=args.note,
                           log=lambda *_: None)
        _print_still_qa(take)
        print(f"Frame index {take['source']['frame']} of {take['source']['frames']} frames; approve it with "
              f"'production take accept --pose {take['owner']['id']} {take['id']}'")
        return
    kind, owner = ("pose", args.pose) if getattr(args, "pose", None) else ("clip", args.clip)
    if args.take_action == "import":
        if kind == "pose":
            from .stills import import_still
            place = tuple(float(v) for v in args.place.split(",")) if args.place else None
            if place is not None and len(place) != 3:
                raise ValueError("--place needs SCALE,DX,DY")
            _print_still_qa(import_still(workspace, owner, args.path, note=args.note, place=place))
        else:
            from .clips import import_clip_take
            take = import_clip_take(workspace, owner, args.path, fps=args.fps, note=args.note)
            print(f"Clip take {take['id']}: {take['media']['count']} frames at {take['media']['fps']:g} fps")
    elif args.take_action == "resume":
        from .clips import resume_clip_take
        take = resume_clip_take(workspace, owner, args.take)
        print(f"Take {take['id']}: {take['state']}")
    elif args.take_action == "note":
        from .records import set_take_note
        set_take_note(workspace, kind, owner, args.take, args.note)
        print(f"Updated note for {kind} take {args.take}")
    elif args.take_action == "process":
        from .render import render_take
        result = render_take(workspace, owner, args.take)
        print(f"Processed {kind} take {args.take}: QA {result['qa']['status']}")
    elif args.take_action == "adopt-processed":
        from .render import adopt_processed_take
        adopt_processed_take(workspace, owner, args.take)
        print(f"Published processed {kind} take {args.take}")
    elif args.take_action == "accept" and kind == "pose":
        from .stills import approve_still
        approve_still(workspace, owner, args.take, args.reason)
        print(f"Approved still {args.take} for pose {owner}")
    else:
        decide(workspace, kind, owner, args.take, args.take_action, args.reason)
        done = {"accept": "Accepted", "reject": "Rejected", "restore": "Restored"}[args.take_action]
        print(f"{done} {kind} take {args.take}")

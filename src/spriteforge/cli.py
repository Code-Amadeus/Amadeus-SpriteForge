from __future__ import annotations
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from .workspace import atomic_json, read_json, resolve_asset


def main() -> int:
    parser = argparse.ArgumentParser(description="SpriteForge asset management and graph editing")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a workspace")
    init.add_argument("workspace", type=Path)
    init.add_argument("--demo", action="store_true", help="Include original geometric example frames")
    review = commands.add_parser("review", help="Open the local asset and graph editor")
    review.add_argument("--workspace", type=Path, required=True)
    review.add_argument("--port", type=int, default=7788)
    review.add_argument("--no-browser", action="store_true")
    review.add_argument("--layout", type=Path, help="Saved authoring graph or companion layout for runtime-pack viewing")
    imp = commands.add_parser("import", help="Copy existing PNG frames into a new workspace project")
    imp.add_argument("--workspace", type=Path, required=True)
    imp.add_argument("--source", type=Path, required=True)
    imp.add_argument("--name", required=True)
    validate = commands.add_parser("validate-graph", help="Validate graph topology and selected frames")
    validate.add_argument("--workspace", type=Path, required=True)
    pack = commands.add_parser("validate-pack", help="Validate the Amadeus runtime character-pack contract")
    pack.add_argument("path", type=Path)
    export = commands.add_parser("export-amadeus", help="Encode selected PNG frames and publish a local runtime package")
    export.add_argument("--workspace", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--id", required=True)
    export.add_argument("--display-name", required=True)
    export.add_argument("--version", required=True)
    export.add_argument("--toktx", default="toktx")
    export.add_argument("--no-mouth", action="store_true", help="Explicitly omit configured mouth overlays")
    qa = commands.add_parser("qa", help="Analyze PNG frames (requires the qa extra)")
    qa.add_argument("root", type=Path)
    qa.add_argument("--output", type=Path, required=True)
    from .production.cli import add_parser as add_production
    add_production(commands)
    args = parser.parse_args()
    try:
        if args.command == "init":
            if args.demo:
                from .demo import create_demo
                create_demo(args.workspace)
            else:
                if args.workspace.exists():
                    raise ValueError("Workspace already exists")
                args.workspace.mkdir(parents=True)
                (args.workspace / "projects").mkdir()
                atomic_json(args.workspace / "graph_config.json", {"nodes": [], "edges": []})
            print(f"Created {args.workspace.resolve()}")
        elif args.command == "review":
            from .server import serve
            serve(args.workspace, args.port, args.no_browser, args.layout)
        elif args.command == "import":
            workspace = args.workspace.resolve()
            if not workspace.is_dir() or not args.source.is_dir():
                raise ValueError("Workspace and source directory must exist")
            if not args.name or args.name in {".", ".."} or any(c in args.name for c in '/\\:'):
                raise ValueError("Project name must be one directory name")
            target = resolve_asset(workspace, f"projects/{args.name}")
            if target.exists():
                raise ValueError("Project already exists; choose a new name")
            source = args.source.resolve()
            frames = sorted(source.rglob("*.png"))
            if not frames:
                raise ValueError("Source has no PNG frames")
            for frame in frames:
                resolve_asset(source, str(frame))
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".import-", dir=target.parent) as temporary:
                staged = Path(temporary) / "project"
                staged.mkdir()
                for frame in frames:
                    dest = staged / frame.relative_to(source)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(frame, dest)
                staged.rename(target)
            print(f"Imported {len(frames)} PNG frames into {target}")
        elif args.command == "validate-graph":
            from .graph import validate_graph
            graph = validate_graph(args.workspace, read_json(resolve_asset(args.workspace, "graph_config.json")))
            print(f"OK: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
        elif args.command == "validate-pack":
            from .character_pack import load_character_pack
            loaded = load_character_pack(args.path)
            print(f"OK: {loaded.manifest['id']}, {len(loaded.clip_paths)} clips")
        elif args.command == "export-amadeus":
            from .exporter import export_pack
            manifest = export_pack(args.workspace, args.output, pack_id=args.id, display_name=args.display_name,
                                   version=args.version, toktx=args.toktx, no_mouth=args.no_mouth)
            print(f"Exported {manifest['clipCount']} clips / {manifest['frameCount']} frames to {args.output.resolve()}")
        elif args.command == "qa":
            from .qa import build_report, write_markdown
            report = build_report(args.root.resolve())
            atomic_json(args.output, report)
            write_markdown(report, args.output.with_suffix(".md"))
            print(f"QA: {report['summary']['status']} -> {args.output}")
        elif args.command == "production":
            from .production.cli import run
            run(args)
        return 0
    except (OSError, ValueError, ImportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

"""Fixed typed candidate workflows, with durable node receipts and dependency caches.

Cache identities describe validated operations and their dependencies, rather
than predicting bytes from a future provider call. Receipts separately preserve
actual artifact hashes and provenance. An explicit rerun changes one identity
and its downstream identities; completed paid receipts never expire.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import uuid
from pathlib import Path

from ..workspace import atomic_json, read_json, resolve_asset
from .media import copy_durable
from .records import check_id, load_character, now, production_dir

FORMAT = "spriteforge.workflow.v1"
RUN_FORMAT = "spriteforge.workflow.run.v1"
NODE_FORMAT = "spriteforge.workflow.node.v1"
TYPES = ("IMAGE", "IMAGES", "VIDEO", "FRAMES", "TEXT", "NUMBER", "POSE", "CLIP")
RUN_LOCK = threading.Lock()
STORE_LOCK = threading.Lock()


def _ops(operations=None):
    if operations is None:
        from . import workflow_ops
        return workflow_ops
    return operations


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def directory(workspace: Path) -> Path:
    return resolve_asset(workspace, str(production_dir(workspace) / "workflows"))


def _path(workspace: Path, *parts: str) -> Path:
    return resolve_asset(workspace, str(directory(workspace).joinpath(*parts)))


def _identifier(value: object, label: str) -> str:
    check_id(value, label)
    return value


def _types(port) -> set[str]:
    raw = port.get("type") if isinstance(port, dict) else port
    values = set(raw) if isinstance(raw, (list, tuple)) else set(str(raw).replace(",", "|").split("|"))
    if not values or values - set(TYPES):
        raise ValueError(f"Unsupported workflow port type {raw!r}")
    return values


def _ports(ops, kind, params) -> tuple[dict, dict]:
    value = ops.ports(kind, params)
    return value["inputs"], value["outputs"]


def _point(value, label, *, positive=False):
    import math
    if not isinstance(value, list) or len(value) != 2 or any(isinstance(item, bool) or not isinstance(item, (int, float))
                                                           or not math.isfinite(item) or (positive and item <= 0) for item in value):
        raise ValueError(f"{label} needs two {'positive ' if positive else ''}finite coordinates")
    return list(value)


def validate_workflow(workspace: Path, raw: object, *, operations=None, executable=False) -> dict:
    ops = _ops(operations)
    fields = {"format", "id", "name", "version", "nodes", "links", "groups", "imported", "disclosedAt"}
    if not isinstance(raw, dict) or set(raw) - fields or raw.get("format") != FORMAT:
        raise ValueError("Unsupported workflow format or fields")
    identifier = _identifier(raw.get("id"), "Workflow")
    if identifier in {"schema", "templates", "runs"}:
        raise ValueError("Workflow id collides with a reserved route")
    name, version = raw.get("name"), raw.get("version", 1)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Workflow needs a name")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("Workflow version must be a positive integer")
    if not isinstance(raw.get("nodes"), list) or not isinstance(raw.get("links"), list):
        raise ValueError("Workflow needs nodes and links arrays")
    result = {"format": FORMAT, "id": identifier, "name": name.strip(), "version": version, "nodes": [], "links": [], "groups": []}
    ids, ports = set(), {}
    for node in raw["nodes"]:
        if not isinstance(node, dict) or set(node) - {"id", "kind", "params", "position", "collapsed"}:
            raise ValueError("Workflow nodes only contain identity, kind, parameters and view coordinates")
        node_id, kind = _identifier(node.get("id"), "Node"), node.get("kind")
        if node_id in ids or not isinstance(kind, str) or kind not in ops.REGISTRY:
            raise ValueError(f"Duplicate node or unknown workflow kind: {node_id} / {kind}")
        params = ops.validate_params(workspace, kind, copy.deepcopy(node.get("params", {})))
        digest(params)  # finite, serializable validated parameters; no executable payload
        inputs, outputs = _ports(ops, kind, params)
        for port in [*inputs.values(), *outputs.values()]:
            _types(port)
        collapsed = node.get("collapsed", False)
        if not isinstance(collapsed, bool):
            raise ValueError("Collapsed must be boolean")
        result["nodes"].append({"id": node_id, "kind": kind, "params": params,
                                "position": _point(node.get("position", [0, 0]), "Node position"), "collapsed": collapsed})
        ids.add(node_id)
        ports[node_id] = inputs, outputs
    occupied = set()
    for link in raw["links"]:
        if not isinstance(link, dict) or set(link) != {"from", "to"}:
            raise ValueError("Workflow links need from/to ports")
        for endpoint in (link["from"], link["to"]):
            if not isinstance(endpoint, dict) or set(endpoint) != {"node", "port"} or endpoint["node"] not in ids \
                    or not isinstance(endpoint["port"], str):
                raise ValueError("Workflow link names an unknown node or port")
        source, target = link["from"], link["to"]
        inputs, outputs = ports[target["node"]][0], ports[source["node"]][1]
        if source["port"] not in outputs or target["port"] not in inputs \
                or not _types(outputs[source["port"]]) & _types(inputs[target["port"]]):
            raise ValueError("Workflow link ports have incompatible types")
        slot = (target["node"], target["port"])
        if slot in occupied:
            raise ValueError("A workflow input can have only one link")
        occupied.add(slot)
        result["links"].append(copy.deepcopy(link))
    for node in result["nodes"]:
        for name, port in ports[node["id"]][0].items():
            if executable and (not isinstance(port, dict) or port.get("required", True)) and (node["id"], name) not in occupied:
                raise ValueError(f"Node {node['id']} requires input {name}")
    topological_order(result)  # cycles cannot dispatch handlers
    if not isinstance(raw.get("groups", []), list):
        raise ValueError("Workflow groups must be an array")
    group_ids = set()
    for group in raw.get("groups", []):
        if not isinstance(group, dict) or set(group) - {"id", "title", "position", "size", "color"}:
            raise ValueError("Workflow groups only contain view geometry and title")
        group_id = _identifier(group.get("id"), "Group")
        if group_id in group_ids or not isinstance(group.get("title"), str) or not isinstance(group.get("color", ""), str):
            raise ValueError("Invalid workflow group")
        result["groups"].append({"id": group_id, "title": group["title"], "position": _point(group.get("position"), "Group position"),
                                 "size": _point(group.get("size"), "Group size", positive=True), "color": group.get("color", "")})
        group_ids.add(group_id)
    return result


def topological_order(workflow: dict) -> list[str]:
    ids = [node["id"] for node in workflow["nodes"]]
    incoming = {node: 0 for node in ids}
    children = {node: [] for node in ids}
    for link in workflow["links"]:
        source, target = link["from"]["node"], link["to"]["node"]
        incoming[target] += 1
        children[source].append(target)
    ready, ordered = [node for node in ids if incoming[node] == 0], []
    while ready:
        node = ready.pop(0)
        ordered.append(node)
        for child in children[node]:
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
    if len(ordered) != len(ids):
        raise ValueError("Workflow must be acyclic")
    return ordered


def load_workflow(workspace: Path, identifier: str, *, operations=None) -> dict:
    path = _path(workspace, f"{_identifier(identifier, 'Workflow')}.json")
    if not path.is_file():
        raise ValueError(f"Unknown workflow {identifier}")
    raw = read_json(path)
    result = validate_workflow(workspace, raw, operations=operations)
    return {**result, "imported": raw.get("imported") is True, "disclosedAt": raw.get("disclosedAt")}


def save_workflow(workspace: Path, raw: object, *, imported=False, operations=None) -> dict:
    result = validate_workflow(workspace, raw, operations=operations)
    load_character(workspace)
    path = _path(workspace, f"{result['id']}.json")
    with STORE_LOCK:
        previous = read_json(path) if path.is_file() else {}
        result["version"] = previous["version"] + 1 if previous else 1
        result["imported"] = imported or previous.get("imported") is True
        result["disclosedAt"] = None if imported else previous.get("disclosedAt")
        atomic_json(path, result)
    return result


def list_workflows(workspace: Path, *, operations=None) -> list[dict]:
    return [{key: workflow.get(key) for key in ("id", "name", "version", "imported", "disclosedAt")}
            | {"requiresDisclosure": workflow["imported"] and not workflow["disclosedAt"]}
            for path in sorted(directory(workspace).glob("*.json"))
            for workflow in [load_workflow(workspace, path.stem, operations=operations)]]


def read_run(workspace: Path, identifier: str) -> dict:
    path = _path(workspace, "runs", _identifier(identifier, "Run"), "run.json")
    if not path.is_file():
        raise ValueError(f"Unknown workflow run {identifier}")
    result = read_json(path)
    if result.get("format") != RUN_FORMAT:
        raise ValueError("Unsupported workflow run format")
    return result


def paid_receipts(workspace: Path) -> list[dict]:
    """The already-required paid node receipts are the single workflow billing ledger."""
    receipts = {}
    for path in sorted((directory(workspace) / "runs").glob("*/*/node.json")):
        value = read_json(resolve_asset(workspace, str(path)))
        if value.get("format") == NODE_FORMAT and value.get("paid") and not value.get("cached") and value.get("operation"):
            receipts[value["cacheKey"]] = value
    return list(receipts.values())


def _artifacts(workspace: Path, outputs: dict) -> list[dict]:
    paths = []
    for asset in outputs.values():
        paths.extend(([asset["path"]] if asset.get("path") else []) + list(asset.get("paths", [])))
        reference = asset.get("record") or {}
        if asset.get("type") in {"POSE", "CLIP"} and reference.get("take"):
            from .records import load_take
            load_take(workspace, reference["kind"], reference["owner"], reference["take"])
    result = []
    for raw in dict.fromkeys(paths):
        path = resolve_asset(workspace, raw)
        if not path.is_file():
            raise ValueError("Workflow output artifact is missing")
        result.append({"path": path.relative_to(workspace).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return result


def _outputs(workspace: Path, outputs: object, ports: dict) -> dict:
    if not isinstance(outputs, dict) or set(outputs) != set(ports):
        raise ValueError("Workflow handler returned unexpected output ports")
    for name, asset in outputs.items():
        if not isinstance(asset, dict) or asset.get("type") not in _types(ports[name]) or not isinstance(asset.get("provenance", {}), dict):
            raise ValueError(f"Workflow output {name} has the wrong asset type or provenance")
    digest(outputs)
    _artifacts(workspace, outputs)
    return copy.deepcopy(outputs)


class WorkflowEngine:
    def __init__(self, workspace: Path, *, operations=None):
        self.workspace = workspace.resolve()
        self.ops = _ops(operations)
        self.plans = {}
        self.lock = threading.Lock()

    def _cache_path(self, key):
        return _path(self.workspace, "cache", f"{key}.json")

    def _heads(self):
        path = _path(self.workspace, "cache", "heads.json")
        return read_json(path) if path.is_file() else {}

    def _build(self, identifier, rerun, nonces):
        workflow = load_workflow(self.workspace, identifier, operations=self.ops)
        validate_workflow(self.workspace, workflow, operations=self.ops, executable=True)
        order = topological_order(workflow)
        if not isinstance(rerun, list) or any(not isinstance(node, str) or node not in order for node in rerun) or len(set(rerun)) != len(rerun):
            raise ValueError("Rerun must list unique workflow node ids")
        nodes, links = {node["id"]: node for node in workflow["nodes"]}, {node: {} for node in order}
        for link in workflow["links"]:
            links[link["to"]["node"]][link["to"]["port"]] = link["from"]
        heads, entries, blocking, owners = self._heads(), {}, [], []
        for node_id in order:
            node = nodes[node_id]
            planned_inputs = {port: entries[ref["node"]]["plannedOutputs"].get(ref["port"])
                              for port, ref in links[node_id].items()}
            in_ports, _ = _ports(self.ops, node["kind"], node["params"])
            for port, asset in planned_inputs.items():
                if asset is not None and asset.get("type") not in _types(in_ports[port]):
                    raise ValueError(f"Node {node_id} has incompatible concrete input type for {port}")
            context = self.ops.context(self.workspace, node["kind"], node["params"], inputs=planned_inputs)
            inputs = {port: {"key": entries[ref["node"]]["cacheKey"], "port": ref["port"]} for port, ref in links[node_id].items()}
            definition = digest({"kind": node["kind"], "params": node["params"], "context": context, "inputs": inputs})
            key = digest({"definition": definition, "rerun": nonces[node_id]}) if node_id in rerun else heads.get(definition, definition)
            path = self._cache_path(key)
            receipt = read_json(path) if path.is_file() else None
            paid = bool(self.ops.REGISTRY[node["kind"]].get("paid"))
            cache_hit, resume = False, False
            if receipt:
                if receipt.get("state") == "ready":
                    try:
                        intact = _artifacts(self.workspace, receipt["outputs"]) == receipt.get("artifacts")
                    except (ValueError, OSError):
                        intact = False
                    if intact:
                        cache_hit = True
                    elif paid:
                        blocking.append({"node": node_id, "reason": "Paid cached artifacts changed or disappeared; explicitly rerun this node"})
                elif paid and receipt.get("operation"):
                    operation = receipt["operation"]
                    resume = bool(operation.get("taskId") and operation.get("state") in {"submitted", "submitting"})
                    if not resume:
                        blocking.append({"node": node_id, "reason": "A paid attempt has no reusable result; explicitly rerun this node"})
            for kind, key_name in (("pose", "pose"), ("clip", "clip")):
                if node["params"].get(key_name):
                    owners.append({"kind": kind, "id": node["params"][key_name]})
            owners.extend(context.get("owners", []))
            if isinstance(node["params"].get("poses"), list):
                owners.extend({"kind": "pose", "id": pose} for pose in node["params"]["poses"])
            provider = node["params"].get("provider")
            entries[node_id] = {"id": node_id, "kind": node["kind"], "definitionKey": definition, "cacheKey": key,
                                "cacheHit": cache_hit, "resume": resume, "paid": paid, "provider": provider,
                                "costType": "credits" if provider == "wan-cli" else "planQuota" if provider == "gpt-image" else "metered",
                                "context": context, "previous": receipt, "inputs": links[node_id], "plannedOutputs": context.get("outputs", {})}
        owners = list({(owner["kind"], owner["id"]): owner for owner in owners}.values())
        paid_nodes = [{"node": entry["id"], "provider": entry["provider"], "costType": entry["costType"]}
                      for entry in entries.values() if entry["paid"] and not entry["cacheHit"] and not entry["resume"]]
        processors = sorted({node["params"]["processor"] for node in nodes.values() if node["kind"] == "external-processor"}
                            | {"alpha" for node in nodes.values() if node["kind"] in {"matte", "normalize", "save-pose-take"}}
                            | {"interpolate" for node in nodes.values() if node["kind"] == "interpolate"})
        fingerprint = digest({"workflow": workflow, "nodes": [{key: entry[key] for key in ("id", "cacheKey", "cacheHit", "resume")}
                                                              for entry in entries.values()], "blocking": blocking})
        return {"workflow": workflow, "order": order, "entries": entries, "rerun": rerun, "nonces": nonces,
                "planHash": fingerprint, "paidCount": len(paid_nodes), "paidNodes": paid_nodes, "processors": processors,
                "owners": owners, "requiresDisclosure": workflow["imported"] and not workflow["disclosedAt"], "blocking": blocking}

    @staticmethod
    def public_plan(plan):
        return {key: plan[key] for key in ("planHash", "paidCount", "paidNodes", "processors", "owners", "requiresDisclosure", "blocking")} | {
            "nodes": [{key: entry[key] for key in ("id", "kind", "cacheHit", "resume", "paid")} for entry in plan["entries"].values()]}

    def plan(self, identifier, *, rerun=None):
        rerun = [] if rerun is None else rerun
        nonces = {node: uuid.uuid4().hex for node in rerun} if isinstance(rerun, list) and all(isinstance(node, str) for node in rerun) else {}
        plan = self._build(identifier, rerun, nonces)
        with self.lock:
            self.plans[plan["planHash"]] = plan
        return self.public_plan(plan)

    def confirmed_plan(self, identifier, plan_hash, confirm_paid, *, confirm_imported=False, rerun=None):
        with self.lock:
            plan = self.plans.get(plan_hash)
        if plan is None or plan["workflow"]["id"] != identifier:
            raise ValueError("Workflow plan is missing; calculate it before running")
        if rerun is not None and rerun != plan["rerun"]:
            raise ValueError("Rerun selection changed; calculate the plan again")
        current = self._build(identifier, plan["rerun"], plan["nonces"])
        if current["planHash"] != plan_hash:
            raise ValueError("Workflow or source/cache facts changed; calculate and confirm the plan again")
        if isinstance(confirm_paid, bool) or not isinstance(confirm_paid, int) or confirm_paid != current["paidCount"]:
            raise ValueError(f"Confirm exactly {current['paidCount']} paid requests before running")
        if current["blocking"]:
            raise ValueError("Workflow has blocked nodes: " + "; ".join(item["reason"] for item in current["blocking"]))
        if current["requiresDisclosure"] and confirm_imported is not True:
            raise ValueError("Confirm the imported workflow's paid nodes and configured processor names before its first run")
        return current

    def _commit_cache(self, receipt, entry):
        receipt["artifacts"] = _artifacts(self.workspace, receipt["outputs"])
        atomic_json(self._cache_path(entry["cacheKey"]), receipt)
        with STORE_LOCK:
            heads = self._heads()
            heads[entry["definitionKey"]] = entry["cacheKey"]
            atomic_json(_path(self.workspace, "cache", "heads.json"), heads)

    def _cached_outputs(self, receipt, node_dir):
        result = copy.deepcopy(receipt["outputs"])
        for port, asset in result.items():
            def copy_path(raw):
                path = resolve_asset(self.workspace, raw)
                if not path.is_relative_to(directory(self.workspace) / "runs"):
                    return raw  # immutable production take/sheet reference
                target = node_dir / port / path.name
                copy_durable(path, target)
                return target.relative_to(self.workspace).as_posix()
            if asset.get("path"):
                asset["path"] = copy_path(asset["path"])
            if "paths" in asset:
                asset["paths"] = [copy_path(path) for path in asset["paths"]]
        return result

    def run(self, identifier, *, plan_hash, confirm_paid, confirm_imported=False, rerun=None, run_id=None, provider_locks=None, log=print):
        if not RUN_LOCK.acquire(blocking=False):
            raise ValueError("A workflow is already running")
        try:
            plan = self.confirmed_plan(identifier, plan_hash, confirm_paid, confirm_imported=confirm_imported, rerun=rerun)
            workflow = plan["workflow"]
            run_id = _identifier(run_id, "Run") if run_id is not None else uuid.uuid4().hex
            run_dir = _path(self.workspace, "runs", run_id)
            run_dir.mkdir(parents=True)
            snapshot = copy.deepcopy(workflow)
            atomic_json(run_dir / "workflow.json", snapshot)
            workflow_ref = {"id": workflow["id"], "version": workflow["version"], "sha256": digest(snapshot)}
            pending = [{"format": NODE_FORMAT, "workflow": workflow_ref, "run": run_id, "node": entry["id"], "kind": entry["kind"],
                        "cacheKey": entry["cacheKey"], "state": "pending", "startedAt": None, "finishedAt": None,
                        "paid": entry["paid"], "cached": entry["cacheHit"], "operation": {}, "inputs": {}, "outputs": {}, "error": None}
                       for entry in plan["entries"].values()]
            run = {"format": RUN_FORMAT, "id": run_id, "workflow": workflow_ref, "state": "running", "startedAt": now(),
                   "finishedAt": None, "error": None, "paidCount": plan["paidCount"], "nodes": pending, "outputs": {}}
            atomic_json(run_dir / "run.json", run)
            if plan["requiresDisclosure"]:
                with STORE_LOCK:
                    path = _path(self.workspace, f"{workflow['id']}.json")
                    saved = read_json(path)
                    saved["disclosedAt"] = now()
                    atomic_json(path, saved)
            nodes = {node["id"]: node for node in workflow["nodes"]}
            results = {}
            for node_id in plan["order"]:
                node, entry = nodes[node_id], plan["entries"][node_id]
                node_dir = run_dir / node_id
                node_dir.mkdir()
                receipt = next(item for item in pending if item["node"] == node_id)
                receipt.update(state="running", startedAt=now())
                if entry["resume"]:
                    receipt["operation"] = copy.deepcopy(entry["previous"]["operation"])
                atomic_json(node_dir / "node.json", receipt)
                atomic_json(run_dir / "run.json", run)
                inputs = {port: results[source["node"]][source["port"]] for port, source in entry["inputs"].items()}
                receipt["inputs"] = copy.deepcopy(inputs)
                in_ports, out_ports = _ports(self.ops, node["kind"], node["params"])
                try:
                    for port, asset in inputs.items():
                        if asset["type"] not in _types(in_ports[port]):
                            raise ValueError(f"Node {node_id} received incompatible concrete input type for {port}")

                    def record(facts):
                        if not isinstance(facts, dict):
                            raise ValueError("Workflow operation checkpoint must be facts")
                        receipt["operation"].update(copy.deepcopy({key: value for key, value in facts.items() if key != "outputs"}))
                        if entry["paid"] and facts.get("state") == "submitting" and not receipt["operation"].get("requestedAt"):
                            receipt["operation"]["requestedAt"] = now()
                        if facts.get("state") == "ready" and "outputs" in facts:
                            receipt["outputs"] = _outputs(self.workspace, facts["outputs"], out_ports)
                            receipt.update(state="ready", finishedAt=now())
                            self._commit_cache(receipt, entry)  # paid success survives later handler/downstream failure
                        elif entry["paid"]:
                            atomic_json(self._cache_path(entry["cacheKey"]), receipt)
                        atomic_json(node_dir / "node.json", receipt)
                        atomic_json(run_dir / "run.json", run)
                        return copy.deepcopy(receipt)

                    log(f"{node_id}: {'cached' if entry['cacheHit'] else 'resuming' if entry['resume'] else 'running'} {node['kind']}")
                    if entry["cacheHit"]:
                        outputs = self._cached_outputs(entry["previous"], node_dir)
                    else:
                        def execute():
                            return self.ops.execute(self.workspace, node_dir, node["kind"], node["params"], inputs, record=record, log=log,
                                                    previous=entry["previous"]["operation"] if entry["resume"] else None)
                        provider_lock = (provider_locks or {}).get(entry["provider"]) if node["kind"] in {"image-edit", "concept-sheet"} else None
                        if provider_lock:
                            log(f"{node_id}: queued for {entry['provider']}; one explicitly confirmed image request")
                            with provider_lock:
                                outputs = execute()
                        else:
                            outputs = execute()
                    receipt["outputs"] = _outputs(self.workspace, outputs, out_ports)
                    receipt.update(state="ready", finishedAt=now())
                    if not entry["cacheHit"]:
                        self._commit_cache(receipt, entry)
                    results[node_id] = receipt["outputs"]
                    atomic_json(node_dir / "node.json", receipt)
                    atomic_json(run_dir / "run.json", run)
                except Exception as exc:
                    receipt.update(state="failed", error=str(exc), finishedAt=now())
                    if entry["paid"] and receipt["operation"] and receipt["operation"].get("state") != "ready":
                        atomic_json(self._cache_path(entry["cacheKey"]), receipt)
                    atomic_json(node_dir / "node.json", receipt)
                    for waiting in pending:
                        if waiting["state"] == "pending":
                            waiting.update(state="skipped", error="Workflow stopped after an upstream failure")
                    run.update(state="failed", error=f"{node_id}: {exc}", finishedAt=now(), outputs=results)
                    atomic_json(run_dir / "run.json", run)
                    raise ValueError(f"Workflow node {node_id} failed: {exc}") from exc
            run.update(state="ready", outputs=results, finishedAt=now())
            atomic_json(run_dir / "run.json", run)
            return run
        finally:
            RUN_LOCK.release()


TEMPLATES = [{"id": identifier, "name": name} for identifier, name in (
    ("transition", "Transition clip"), ("loop", "Loop clip"), ("speaking", "Speaking loop"),
    ("final-still", "Final still without concept"), ("concept-still", "Concept sheet to final still"))]


def schema(workspace: Path, *, operations=None) -> dict:
    from .providers import provider_status
    from .records import list_owners
    from .tools import load_tools
    ops = _ops(operations)
    kinds = ops.public_registry(workspace)
    poses, clips = list_owners(workspace, "pose"), list_owners(workspace, "clip")
    for kind in kinds:
        for name, param in kind["params"].items():
            if name in {"pose", "clip"}:
                param["choices"] = ([""] if not param.get("required") else []) + [owner["id"] for owner in (poses if name == "pose" else clips)]
    tools = load_tools(workspace)
    providers = {name: {"model": config.get("model"), **provider_status(name, config)} for name, config in tools["providers"].items()}
    return {"types": list(TYPES), "nodeKinds": kinds, "templates": copy.deepcopy(TEMPLATES), "providers": providers}


def template_workflow(workspace: Path, template: str, *, pose=None, clip=None, concept=None, identifier=None, operations=None) -> dict:
    """Prefill an ordinary editable graph from current production facts, without writes."""
    from .records import list_owners, load_owner
    from .tools import load_tools
    if template not in {item["id"] for item in TEMPLATES}:
        raise ValueError("Unknown workflow template")
    character, tools = load_character(workspace), load_tools(workspace)
    nodes, links = [], []

    def node(identifier, kind, params=None):
        index = len(nodes)
        nodes.append({"id": identifier, "kind": kind, "params": params or {},
                      "position": [60 + (index % 3) * 340, 100 + (index // 3) * 460]})
        return identifier

    def link(source, output, target, input_):
        links.append({"from": {"node": source, "port": output}, "to": {"node": target, "port": input_}})

    if template in {"transition", "loop", "speaking"}:
        matches = [owner for owner in list_owners(workspace, "clip") if (owner["kind"] == "transition") == (template == "transition")
                   and (template != "speaking" or owner.get("mouth"))]
        owner = load_owner(workspace, "clip", clip) if clip else matches[0] if matches else None
        if owner is None:
            raise ValueError("Plan a matching production clip before opening this workflow template")
        if (owner["kind"] == "transition") != (template == "transition") or template == "speaking" and not owner.get("mouth"):
            raise ValueError("Clip does not match this workflow template")
        generation = owner["generation"]
        if generation["provider"] == "manual":
            if not owner.get("acceptedTake"):
                raise ValueError("Manual clip workflow needs an existing ready take")
            source = node("source", "clip-take", {"clip": owner["id"], "take": owner["acceptedTake"]})
            save = node("candidate", "save-clip-take", {"clip": owner["id"], "note": "Local workflow candidate"})
            link(source, "media", save, "media")
        else:
            start = node("first", "approved-still", {"pose": owner["from"]})
            prompt = node("prompt", "prompt-template", {"template": owner["kind"], "clip": owner["id"]})
            video = node("generate", "video-from-frames", {**{key: generation[key] for key in ("provider", "durationS", "resolution")},
                         "seed": generation.get("seed"), "inputScale": generation.get("inputScale", 1.0)})
            link(start, "image", video, "first")
            link(prompt, "text", video, "prompt")
            if generation.get("lastFrame", "still") == "still":
                end = node("last", "approved-still", {"pose": owner["to"]})
                link(end, "image", video, "last")
            save = node("candidate", "save-clip-take", {"clip": owner["id"]})
            link(video, "video", save, "media")
    else:
        pose = pose or next((owner["id"] for owner in list_owners(workspace, "pose") if owner["id"] != character["basePose"]), character["basePose"])
        load_owner(workspace, "pose", pose)
        base = node("base", "base-still")
        reference = None
        if concept is not None:
            from .concepts import concept_reference
            if not isinstance(concept, dict) or set(concept) != {"sheet", "cell"}:
                raise ValueError("Workflow concept reference needs sheet and cell")
            concept_reference(workspace, concept["sheet"], concept["cell"], pose)
            reference = node("reference", "concept-cell", concept)
        elif template == "concept-still":
            prompt = node("concept-prompt", "prompt-template", {"template": "concept", "poses": [pose], "grid": "3x2"})
            sheet = node("concept-generate", "concept-sheet", {"provider": tools["defaults"]["conceptProvider"], "grid": "3x2"})
            link(base, "image", sheet, "image")
            link(prompt, "text", sheet, "prompt")
            saved = node("concept-save", "save-concept-sheet", {"poses": [pose], "grid": "3x2"})
            link(sheet, "image", saved, "image")
            reference = node("reference", "select-image", {"index": 0})
            link(saved, "images", reference, "images")
        prompt = node("prompt", "prompt-template", {"template": "still-reference" if reference else "still", "pose": pose})
        image = node("generate", "image-edit", {"provider": tools["defaults"]["stillProvider"]})
        link(base, "image", image, "image")
        link(prompt, "text", image, "prompt")
        if reference:
            link(reference, "image", image, "reference")
        saved = node("candidate", "save-pose-take", {"pose": pose})
        link(image, "image", saved, "image")
    raw = {"format": FORMAT, "id": identifier or f"{template}-{uuid.uuid4().hex[:8]}", "name": next(item["name"] for item in TEMPLATES if item["id"] == template),
           "version": 1, "nodes": nodes, "links": links, "groups": []}
    return validate_workflow(workspace, raw, operations=operations)

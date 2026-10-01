"""Runtime route invariants, without importing Amadeus or touching media."""
import copy

import pytest

from spriteforge.behavior import (first_hop_to_any, mulberry32, path_to_any, pose_coverage,
                                 root_node, simulate, topology_summary)


def graph(ids, edges, **changes):
    return {"nodes": [{"id": name, "label": name, **changes.get(name, {})} for name in ids],
            "edges": [{"id": f"e{i}", "from": a, "to": b, "prob": prob} for i, (a, b, prob) in enumerate(edges)]}


def test_seeded_rng_and_root_match_runtime_order():
    random = mulberry32(1)
    assert [random(), random()] == [0.6270739405881613, 0.002735721180215478]
    raw = graph(["first", "root"], [], root={"isRoot": True})
    assert root_node(raw) == "root"
    raw["nodes"][1].pop("isRoot")
    assert root_node(raw) == "first"
    assert root_node(graph([], [])) is None
    for seed in (True, -1, 2**32, 1.0):
        with pytest.raises(ValueError):
            mulberry32(seed)


def test_manual_first_hop_and_direct_target_priority_preserve_saved_ties():
    raw = graph(["root", "auto", "manual", "target"], [
        ("root", "auto", 1), ("root", "manual", 0), ("auto", "target", 1), ("manual", "target", 1)])
    assert path_to_any(raw, "root", {"target"}) == ["root", "manual", "target"]
    raw["edges"].append({"id": "direct", "from": "root", "to": "target", "prob": 1})
    assert first_hop_to_any(raw, "root", {"target"}) == "target"
    assert first_hop_to_any(raw, "target", {"target"}) == "target"
    raw["edges"] = [edge for edge in raw["edges"] if edge["id"] != "direct"]
    raw["edges"][2]["prob"] = raw["edges"][3]["prob"] = 0
    assert path_to_any(raw, "root", {"target"}) is None
    ties = graph(["root", "a", "b", "target"], [("root", "b", 0), ("root", "a", 0),
                                                ("a", "target", 1), ("b", "target", 1)])
    assert first_hop_to_any(ties, "root", {"target"}) == "b"


def test_idle_never_uses_manual_edges_and_accounts_partial_final_clip():
    raw = graph(["root", "manual"], [("root", "root", 1), ("root", "manual", 0)])
    result = simulate(raw, {}, seconds=6, seed=4, trace=True)
    assert result["nodeTime"] == {"root": 6, "manual": 0}
    assert [part["durationS"] for part in result["route"]] == [2.5, 2.5, 1]
    assert result["nodeVisits"] == {"root": 3, "manual": 0}
    assert result["changes"] == 0 and result["autoEdgesUsed"] == ["e0"]
    empty = simulate(graph([], []), {}, seconds=600)
    assert empty["seconds"] == 0 and empty["route"] == []


def test_topology_separates_manual_reachability_and_hold_dead_ends():
    raw = graph(["root", "intent", "hold", "lost"], [("root", "root", 1), ("root", "intent", 0),
                                                      ("intent", "hold", 1)], hold={"loopMode": "once_then_hold"})
    assert topology_summary(raw) == {"unreachable": ["lost"], "intentOnly": ["intent", "hold"],
                                     "deadEnds": ["hold"], "intentExitLoops": ["lost"]}


def test_100k_steps_time_occupancy_matches_weighted_stationary_distribution():
    raw = graph(["root", "other"], [("root", "root", 1), ("root", "other", 3), ("other", "root", 1)])
    result = simulate(raw, {"root": 1, "other": 3}, steps=100_000, seed=123)
    assert abs(result["nodeTime"]["root"] / result["seconds"] - 4 / 13) < .02
    assert abs(result["nodeTime"]["other"] / result["seconds"] - 9 / 13) < .02
    assert result == simulate(raw, {"root": 1, "other": 3}, steps=100_000, seed=123)
    moved = copy.deepcopy(raw)
    for node in moved["nodes"]:
        node.update(x=9999, y=-12)
    assert result == simulate(moved, {"root": 1, "other": 3}, steps=100_000, seed=123)


def test_trigger_forces_only_first_hop_then_reports_actual_target_visit():
    raw = graph(["root", "branch", "target", "sink"], [("root", "branch", 0), ("branch", "target", 1),
                                                         ("branch", "sink", 100), ("sink", "sink", 1)])
    result = simulate(raw, dict.fromkeys(("root", "branch", "target", "sink"), 1), seconds=5, seed=1,
                      events=[{"atS": 0, "label": "target"}], trace=True, failing_edges={"e0"})
    event = result["events"][0]
    assert event["path"] == ["root", "branch", "target"] and event["reachable"]
    assert event["appliedAtS"] == 1 and event["from"] == "root"
    assert not event["reached"] and event["visitedTargets"] == []
    assert [part["node"] for part in result["route"]] == ["root", "branch", "sink", "sink", "sink"]
    assert result["jumps"] == ["e0"] and result["route"][1]["seamFail"]
    raw["edges"][2]["prob"] = 0
    result = simulate(raw, {}, seconds=12, events=[{"atS": 0, "speech": True}], speech_targets={"target"})
    assert result["events"][0]["reached"] and result["events"][0]["visitedTargets"] == ["target"]


def test_unreachable_events_never_teleport_and_late_events_remain_unapplied():
    raw = graph(["root", "target"], [("root", "root", 1)])
    result = simulate(raw, {"root": 2}, seconds=5, events=[{"atS": 0, "label": "target"},
                                                        {"atS": 4.5, "label": "root"}], trace=True)
    assert all(part["node"] == "root" for part in result["route"])
    assert result["events"][0]["path"] == [] and not result["events"][0]["reachable"]
    assert result["events"][1]["appliedAtS"] is None and result["events"][1]["path"] == []


@pytest.mark.parametrize("event", [{"atS": True, "label": "root"}, {"atS": float("nan"), "label": "root"},
                                  {"atS": 10, "label": "root"}, {"atS": 0, "speech": False},
                                  {"atS": 0, "speech": True, "label": "root"}, {"atS": 0, "label": ""}])
def test_invalid_trigger_facts_are_rejected(event):
    with pytest.raises(ValueError):
        simulate(graph(["root"], []), {}, seconds=10, events=[event])


def test_coverage_availability_and_graph_membership_are_separate():
    def clip(name, source, target, *, kind="transition", mouth=None, state="current", qa="pass", accepted="yes"):
        return {"id": name, "from": source, "to": target, "kind": kind, "mouth": mouth,
                "acceptedTake": accepted, "render": {"state": state, "qa": {"status": qa}}}
    clips = [clip("enter", "idle", "smile", qa="watch"), clip("loop", "smile", "smile", kind="loop", qa="fix"),
             clip("speaking", "smile", "smile", kind="loop", mouth={"set": "neutral"}, qa="fail"),
             clip("exit", "smile", "idle", state="stale")]
    rows = pose_coverage([{"id": "idle"}, {"id": "smile"}], clips, {"n": "enter"}, "idle")
    assert not rows[0]["enter"]["applicable"] and not rows[0]["exit"]["applicable"]
    assert rows[1]["inGraph"] and rows[1]["enter"]["available"] == rows[1]["loop"]["available"] == 1
    assert rows[1]["speaking"]["available"] == rows[1]["exit"]["available"] == 0
    assert rows[1]["speaking"]["level"] == "fail" and rows[1]["speaking"]["clips"] == ["speaking"]

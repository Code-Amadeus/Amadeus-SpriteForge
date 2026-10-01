"""Operation authority and durable output contracts, using synthetic pixels only."""
from copy import deepcopy
import hashlib
from pathlib import Path

import numpy as np
import pytest

from synthetic import frame_folder, save, still
from spriteforge.production import workflow_ops as ops
from spriteforge.production import concepts, prompts
from spriteforge.production.clips import import_clip_take
from spriteforge.production.media import encode_png, read_bgra
from spriteforge.production.project import add_clip, add_pose
from spriteforge.production.records import load_owner, list_takes, still_path
from spriteforge.production.tools import load_tools, save_tools
from spriteforge.production.workflows import WorkflowEngine, read_run, save_workflow
from spriteforge.workspace import atomic_json


class Recorder:
    def __init__(self):
        self.calls=[]
        self.receipt={"workflow":{"id":"synthetic","version":1,"sha256":"a"*64},"run":"run","node":"node","cacheKey":"b"*64}

    def __call__(self,facts):
        self.calls.append(deepcopy(facts))
        return self.receipt


def run(studio,kind,params=None,inputs=None,record=None):
    return ops.execute(studio.root,studio.root/"production/workflows/test"/f"{kind}-{len(list(studio.root.rglob('node.json')))}",
                       kind,ops.validate_params(studio.root,kind,params or {}),inputs or {},record=record or Recorder(),log=lambda *_:None)


def approved(studio,pose="idle"):
    return run(studio,"approved-still",{"pose":pose})["image"]


def prompt(studio,text="Synthetic instruction"):
    return run(studio,"text",{"text":text})["text"]


def test_readonly_reroute_and_preview_keep_canonical_authority(studio):
    base=approved(studio)
    routed=run(studio,"reroute",{"type":"IMAGE"},{"input":base})["output"]
    preview=run(studio,"preview",inputs={"media":routed})["media"]
    ops._approved_base(studio.root,preview)
    assert preview==base and ops.ports("reroute",{"type":"IMAGE"})["outputs"]["output"]=="IMAGE"


@pytest.mark.parametrize("mutation",["concept","candidate","load","changed","transformed","identity"])
def test_generation_rejects_unapproved_or_changed_inputs_before_provider_call(studio,monkeypatch,mutation):
    calls=[]
    class Adapter:
        model="fake"
        negative_prompt=True
        supports_reference=True
        def key(self):calls.append("key")
        def preview(self,job):return {}
        def submit(self,job):calls.append("submit");raise AssertionError("Must not submit")
        def edit(self,job):calls.append("edit");raise AssertionError("Must not edit")
    monkeypatch.setattr(ops,"get_provider",lambda *_:Adapter())
    monkeypatch.setattr(ops,"get_image_provider",lambda *_:Adapter())
    asset=approved(studio)
    if mutation=="concept":asset["provenance"]["conceptual"]=True
    elif mutation=="candidate":asset["provenance"]={"conceptual":False}
    elif mutation=="load":asset=run(studio,"load-image",{"path":asset["path"]})["image"]
    elif mutation=="changed":
        path=studio.root/"changed.png";path.write_bytes(encode_png(still(studio,"smile")))
        asset.update(path="changed.png",sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    elif mutation=="transformed":
        descriptor=ops.context(studio.root,"scale",{"factor":2},inputs={"media":asset})["outputs"]["media"]
        with pytest.raises(ValueError,match="canonical"):
            ops.context(studio.root,"image-edit",{},inputs={"image":descriptor,"prompt":prompt(studio)})
        asset=run(studio,"scale",{"factor":2},{"media":asset})["media"]
    else:asset["provenance"]["still"]="not-current"
    for kind,inputs in [("image-edit",{"image":asset,"prompt":prompt(studio)}),
                        ("video-from-frames",{"first":asset,"prompt":prompt(studio)})]:
        with pytest.raises(ValueError,match="approved|canonical"):
            ops.context(studio.root,kind,{},inputs=inputs)
        with pytest.raises(ValueError,match="approved|canonical"):
            run(studio,kind,inputs=inputs)
    assert not {"edit","submit"} & set(calls)


def test_video_valid_approved_stills_and_exact_scaled_input_receipt(studio,monkeypatch):
    jobs=[]
    class Adapter:
        model="fake";negative_prompt=True;timeout_seconds=1;poll_seconds=0
        def key(self):pass
        def balance(self):return {"balance":10-len(jobs)}
        def preview(self,job):return {"first":hashlib.sha256(job.first).hexdigest(),"last":hashlib.sha256(job.last).hexdigest()}
        def submit(self,job):jobs.append(job);return "task"
        def poll(self,task):return "succeeded","fake", ""
        def fetch_result(self,task,url,target):target.write_bytes(b"synthetic durable video")
    monkeypatch.setattr(ops,"get_provider",lambda *_:Adapter())
    monkeypatch.setattr(ops,"video_info",lambda _:{"fps":30,"count":3,"width":240,"height":320})
    record=Recorder()
    outputs=run(studio,"video-from-frames",{"inputScale":.75},
                {"first":approved(studio),"last":approved(studio,"smile"),"prompt":prompt(studio)},record)
    assert len(jobs)==1 and jobs[0].seed is None
    submitted=next(f for f in record.calls if f.get("state")=="submitted")
    for role,data in [("first",jobs[0].first),("last",jobs[0].last)]:
        assert (studio.root/submitted["inputs"][role]["path"]).read_bytes()==data
    assert outputs["video"]["type"]=="VIDEO" and record.calls[-1]["state"]=="ready"


def test_text_join_preserves_negative_snapshot_and_placeholder_gate(studio,monkeypatch):
    raw=prompt(studio,"{{PLACEHOLDER: describe motion}}")
    raw["prompt"]={"text":raw["text"],"negative":"negative","blocks":{"subject":1}}
    joined=run(studio,"join-text",inputs={"a":raw,"b":prompt(studio,"tail")})["text"]
    assert joined["prompt"]["negative"]=="negative" and len(joined["prompt"]["parts"])==2
    with pytest.raises(ValueError,match="placeholder|Incomplete|incomplete"):
        ops.context(studio.root,"image-edit",{},inputs={"image":approved(studio),"prompt":joined})


def test_concept_origin_survives_split_select_transform_qa_and_blocks_pose_sink(studio):
    add_pose(studio.root,"new-pose")
    sheet=concepts.import_sheet(studio.root,studio.tmp/"master.png",["new-pose"],"3x2")
    image=run(studio,"concept-cell",{"sheet":sheet["id"],"cell":0})["image"]
    images=run(studio,"split-grid",{"grid":"2x2"},{"image":image})["images"]
    visible_index=next(index for index,path in enumerate(images["paths"]) if np.any(read_bgra(studio.root/path)[0][:,:,3]))
    selected=run(studio,"select-image",{"index":visible_index},{"images":images})["image"]
    scaled=run(studio,"scale",{"factor":1},{"media":selected})["media"]
    qa=run(studio,"still-qa",{"pose":"new-pose"},{"image":scaled})["image"]
    with pytest.raises(ValueError,match="Concept"):
        run(studio,"save-pose-take",{"pose":"new-pose"},{"image":qa})
    assert not list_takes(studio.root,"pose","new-pose")
    descriptor={"type":"IMAGE","provenance":{"conceptual":True}}
    known=ops.context(studio.root,"still-qa",{"pose":"new-pose"},inputs={"image":descriptor})["outputs"]["image"]
    with pytest.raises(ValueError,match="Concept"):
        ops.context(studio.root,"save-pose-take",{"pose":"new-pose"},inputs={"image":known})


def test_loading_a_concept_workflow_artifact_keeps_host_receipt_origin(studio):
    folder=studio.root/"production/workflows/runs/synthetic/sheet";folder.mkdir(parents=True)
    path=folder/"source.png";path.write_bytes(encode_png(still(studio,"idle")))
    atomic_json(folder/"node.json",{"format":"spriteforge.workflow.node.v1","operation":{"conceptual":True},"outputs":{}})
    asset=run(studio,"load-image",{"path":path.relative_to(studio.root).as_posix()})["image"]
    assert asset["provenance"]["conceptual"] is True


def test_approved_concept_target_is_blocked_during_planning(studio):
    with pytest.raises(ValueError,match="approved"):
        ops.context(studio.root,"save-concept-sheet",{"poses":["smile"],"grid":"3x2"})


def test_sink_failed_history_is_not_success_and_ready_qa_fail_is_candidate(studio,monkeypatch):
    from spriteforge.production import stills
    add_pose(studio.root,"new-pose")
    monkeypatch.setattr(stills,"import_still",lambda *a,**k:{"state":"failed","error":"recorded failure","id":"failed"})
    with pytest.raises(ValueError,match="recorded failure"):
        run(studio,"save-pose-take",{"pose":"new-pose"},{"image":approved(studio)})
    monkeypatch.setattr(stills,"import_still",lambda *a,**k:{"state":"ready","qa":{"status":"fail"},"id":"candidate"})
    asset=run(studio,"save-pose-take",{"pose":"new-pose"},{"image":approved(studio)})["pose"]
    assert asset["record"]["take"]=="candidate" and load_owner(studio.root,"pose","new-pose")["acceptedTake"] is None


def test_workspace_and_processor_authority_and_finite_params(studio):
    for path in ["../master.png",str(studio.tmp/"master.png")]:
        with pytest.raises(ValueError):ops.validate_params(studio.root,"load-image",{"path":path})
    with pytest.raises(ValueError):ops.validate_params(studio.root,"external-processor",{"processor":"not-configured","command":["evil"]})
    with pytest.raises(ValueError):ops.validate_params(studio.root,"scale",{"factor":float("nan")})
    assert ops.validate_params(studio.root,"video-from-frames",{})["seed"] is None


def test_frames_reverse_trim_and_save_remain_candidate_and_do_not_publish(studio):
    add_clip(studio.root,"new-clip","idle","smile")
    take=import_clip_take(studio.root,"new-clip",frame_folder(studio,"raw-frames","idle","smile",3),fps=30)
    source=run(studio,"clip-take",{"clip":"new-clip","take":take["id"]})["media"]
    reversed_=run(studio,"reverse",inputs={"media":source})["media"]
    assert (studio.root/reversed_["paths"][0]).read_bytes()==(studio.root/source["paths"][-1]).read_bytes()
    result=run(studio,"save-clip-take",{"clip":"new-clip"},{"media":reversed_})["clip"]
    assert result["record"]["take"]!=take["id"] and load_owner(studio.root,"clip","new-clip")["acceptedTake"] is None
    assert not (studio.root/"production/clips/new-clip/output").exists()


def test_actual_paid_receipt_survives_sink_failure_without_another_image_call(studio,monkeypatch):
    from spriteforge.production import stills
    add_pose(studio.root,"new-pose")
    calls=[]
    class Adapter:
        model="fake";negative_prompt=True;supports_reference=True
        def key(self):pass
        def preview(self,job):return {"image":hashlib.sha256(job.image).hexdigest(),"prompt":job.prompt}
        def edit(self,job):calls.append(job);return encode_png(still(studio,"idle")[:,:,:3])
    monkeypatch.setattr(ops,"get_image_provider",lambda *_:Adapter())
    monkeypatch.setattr(stills,"matte",lambda *_:(_ for _ in ()).throw(ValueError("synthetic alpha failure")))
    raw={"format":"spriteforge.workflow.v1","id":"durable-paid","name":"Durable paid","version":1,
         "nodes":[{"id":"base","kind":"base-still","params":{},"position":[0,0]},
                  {"id":"prompt","kind":"text","params":{"text":"Synthetic complete instruction"},"position":[0,100]},
                  {"id":"paid","kind":"image-edit","params":{},"position":[100,0]},
                  {"id":"save","kind":"save-pose-take","params":{"pose":"new-pose"},"position":[200,0]}],
         "links":[{"from":{"node":"base","port":"image"},"to":{"node":"paid","port":"image"}},
                  {"from":{"node":"prompt","port":"text"},"to":{"node":"paid","port":"prompt"}},
                  {"from":{"node":"paid","port":"image"},"to":{"node":"save","port":"image"}}]}
    save_workflow(studio.root,raw)
    engine=WorkflowEngine(studio.root);plan=engine.plan(raw["id"])
    with pytest.raises(ValueError,match="synthetic alpha failure"):
        engine.run(raw["id"],plan_hash=plan["planHash"],confirm_paid=1,run_id="failed-proof",log=lambda *_:None)
    failed=read_run(studio.root,"failed-proof")
    assert failed["state"]=="failed" and len(calls)==1
    assert list_takes(studio.root,"pose","new-pose")[0]["state"]=="failed"
    monkeypatch.setattr(stills,"matte",lambda *_:still(studio,"idle"))
    plan=engine.plan(raw["id"]);assert plan["paidCount"]==0
    ready=engine.run(raw["id"],plan_hash=plan["planHash"],confirm_paid=0,log=lambda *_:None)
    assert ready["state"]=="ready" and len(calls)==1
    assert {take["state"] for take in list_takes(studio.root,"pose","new-pose")}=={"failed","ready"}
    assert load_owner(studio.root,"pose","new-pose")["acceptedTake"] is None


def test_submitted_video_receipt_resumes_download_without_resubmission(studio,monkeypatch):
    submissions=[];downloads=[]
    class Adapter:
        model="fake";negative_prompt=True;timeout_seconds=1;poll_seconds=0
        def key(self):pass
        def balance(self):return {"balance":10-len(submissions)}
        def preview(self,job):return {"prompt":job.prompt}
        def submit(self,job):submissions.append(job);return "existing-task"
        def poll(self,task):return "succeeded","fake",""
        def fetch_result(self,task,url,target):
            downloads.append(task)
            if len(downloads)==1:raise ValueError("synthetic interrupted download")
            target.write_bytes(b"synthetic durable video")
    monkeypatch.setattr(ops,"get_provider",lambda *_:Adapter())
    monkeypatch.setattr(ops,"video_info",lambda _:{"fps":30,"count":3,"width":240,"height":320})
    inputs={"first":approved(studio),"prompt":prompt(studio)};record=Recorder()
    with pytest.raises(ValueError,match="interrupted"):
        run(studio,"video-from-frames",inputs=inputs,record=record)
    previous=record.calls[-1];assert previous["state"]=="submitted" and previous["taskId"]=="existing-task"
    result=ops.execute(studio.root,studio.root/"production/workflows/resume","video-from-frames",{},inputs,
                       record=Recorder(),log=lambda *_:None,previous=previous)
    assert result["video"]["type"]=="VIDEO" and len(submissions)==1 and downloads==["existing-task"]*2


@pytest.mark.parametrize("kind,processor",[("matte","alpha"),("interpolate","interpolate")])
def test_explicit_unconfigured_processor_blocks_plan_before_paid_call(studio,monkeypatch,kind,processor):
    calls=[]
    class Adapter:
        model="fake";negative_prompt=True;supports_reference=True
        def edit(self,job):calls.append(job);raise AssertionError("Must not call a provider")
    monkeypatch.setattr(ops,"get_image_provider",lambda *_:Adapter())
    tools=load_tools(studio.root);tools[processor]=None;save_tools(studio.root,tools)
    with pytest.raises(ValueError,match=f"'{processor}' processor is configured"):
        ops.context(studio.root,kind,{})
    # Matte receives a future provider image; configuration alone proves that
    # this graph cannot run, without probing a command or GPU.
    if kind=="matte":
        raw={"format":"spriteforge.workflow.v1","id":"missing-alpha","name":"Missing alpha","version":1,
             "nodes":[{"id":"base","kind":"base-still","params":{},"position":[0,0]},
                      {"id":"prompt","kind":"text","params":{"text":"Synthetic complete instruction"},"position":[0,100]},
                      {"id":"paid","kind":"image-edit","params":{},"position":[100,0]},
                      {"id":"matte","kind":"matte","params":{},"position":[200,0]}],
             "links":[{"from":{"node":"base","port":"image"},"to":{"node":"paid","port":"image"}},
                      {"from":{"node":"prompt","port":"text"},"to":{"node":"paid","port":"prompt"}},
                      {"from":{"node":"paid","port":"image"},"to":{"node":"matte","port":"media"}}]}
        save_workflow(studio.root,raw)
        with pytest.raises(ValueError,match="'alpha' processor is configured"):
            WorkflowEngine(studio.root).plan(raw["id"])
    assert not calls

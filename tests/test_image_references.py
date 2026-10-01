"""New image-provider boundaries, using fake HTTP and fake Codex processes only."""
import base64
import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

from spriteforge.production.project import add_pose
from spriteforge.production.providers import ImageJob, get_image_provider, provider_status
from spriteforge.production.records import list_takes, load_character, load_owner, take_dir, take_status
from spriteforge.production.stills import generate_still, set_expected, still_input
from spriteforge.production.tools import load_tools, save_tools
from test_providers import edited_still, providers, quiet, write_prompts  # shared fake HTTP fixture


@pytest.mark.parametrize("provider,expected", [("qwen-image", "512*512"), ("seedream", "960x960")])
def test_http_reference_request_uses_two_images_and_legal_explicit_size(studio, providers, provider, expected):
    tools = load_tools(studio.root)
    adapter = get_image_provider(provider, tools)
    image, _ = still_input(studio.root, load_character(studio.root))
    reference = edited_still(studio)
    providers.edited = reference
    job = ImageJob("Use the expression in image 2, preserve image 1 geometry", "", image, references=[reference], size=(512, 512))
    assert adapter.edit(job) == reference
    body = providers.requests[0][3]
    if provider == "qwen-image":
        content = body["input"]["messages"][0]["content"]
        sent = [entry["image"] for entry in content if "image" in entry]
        assert content[-1] == {"text": job.prompt}
        assert body["parameters"]["size"] == expected
    else:
        sent = body["image"]
        assert body["size"] == expected
    assert [base64.b64decode(value.split(",", 1)[1]) for value in sent] == [image, reference]
    preview = adapter.preview(job)
    assert "data:image" not in json.dumps(preview)
    assert provider_status(provider, tools["providers"][provider])["supportsReference"] is True


@pytest.fixture
def codex_fake(studio, monkeypatch, tmp_path):
    folder = tmp_path / "codex-process"
    home = tmp_path / "codex-home"
    folder.mkdir(); home.mkdir()
    source = folder / "result-source.png"
    source.write_bytes(edited_still(studio))
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("FAKE_CODEX_STATE", str(folder))
    monkeypatch.setenv("FAKE_CODEX_IMAGE", str(source))
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-forwarded")
    monkeypatch.setenv("CODEX_API_KEY", "synthetic-not-forwarded")
    tools = load_tools(studio.root)
    tools["providers"]["gpt-image"].update(command=[sys.executable, str(Path(__file__).parent / "processors" / "fake_codex_cli.py")])
    save_tools(studio.root, tools)
    add_pose(studio.root, "grin", "wide grin")
    write_prompts(studio)
    return folder, home, source


def codex_calls(folder):
    return [json.loads(line) for line in (folder / "calls.jsonl").read_text(encoding="utf-8").splitlines()]


def test_codex_one_isolated_request_uses_native_thread_image_without_auth_reads(studio, codex_fake):
    folder, home, source = codex_fake
    take = generate_still(studio.root, "grin", "gpt-image", log=quiet)
    [call] = codex_calls(folder)
    args = call["args"]
    assert args[0] == "exec" and all(flag in args for flag in ("--ignore-user-config", "--ephemeral", "--skip-git-repo-check", "--json"))
    assert args[args.index("--cd") + 1] == call["cwd"]
    assert call["apiEnvironmentPresent"] is False
    assert "Do not use shell, exec" in call["prompt"] and "Do not read or write configuration" in call["prompt"]
    assert {entry["name"] for entry in call["images"]} == {"input.png"}
    directory = take_dir(studio.root, "pose", "grin", take["id"])
    assert (directory / "source.png").read_bytes() == source.read_bytes()
    assert take["state"] == "ready" and take_status(load_owner(studio.root, "pose", "grin"), take) == "candidate" and take["prompt"]["negativeSent"] is False
    assert {path.name for path in home.iterdir()} == {"generated_images"}
    status = provider_status("gpt-image", load_tools(studio.root)["providers"]["gpt-image"])
    assert status == {"credential": "command", "keySet": True, "supportsReference": True, "costType": "planQuota"}
    assert len(codex_calls(folder)) == 1, "Overview readiness must not invoke an authentication probe"


def test_codex_actual_valid_image_wins_over_model_dimension_error(studio, codex_fake, monkeypatch):
    folder, _, source = codex_fake
    monkeypatch.setenv("FAKE_CODEX_MODE", "narration-error")
    take = generate_still(studio.root, "grin", "gpt-image", log=quiet)
    assert take["state"] == "ready"
    assert (take_dir(studio.root, "pose", "grin", take["id"]) / "source.png").read_bytes() == source.read_bytes()
    assert len(codex_calls(folder)) == 1


@pytest.mark.parametrize("mode", ["auth", "quota", "other-thread", "outside", "bad-png", "truncated-png", "no-thread", "duplicate-thread", "no-image"])
def test_codex_failures_are_observable_failed_takes_and_never_retry(studio, codex_fake, monkeypatch, mode):
    folder, _, _ = codex_fake
    monkeypatch.setenv("FAKE_CODEX_MODE", mode)
    with pytest.raises(ValueError):
        generate_still(studio.root, "grin", "gpt-image", log=quiet)
    [take] = list_takes(studio.root, "pose", "grin")
    assert take["state"] == "failed" and take_status(load_owner(studio.root, "pose", "grin"), take) == "failed" and take.get("error")
    assert load_owner(studio.root, "pose", "grin")["acceptedTake"] is None
    assert (take_dir(studio.root, "pose", "grin", take["id"]) / "input.png").is_file()
    assert len(codex_calls(folder)) == 1


def test_codex_missing_command_fails_before_creating_a_take(studio, codex_fake):
    folder, _, _ = codex_fake
    tools = load_tools(studio.root)
    tools["providers"]["gpt-image"]["command"] = [str(folder / "missing-executable")]
    save_tools(studio.root, tools)
    with pytest.raises(ValueError, match="command"):
        generate_still(studio.root, "grin", "gpt-image", log=quiet)
    assert list_takes(studio.root, "pose", "grin") == []
    assert not (folder / "calls.jsonl").exists()


def test_codex_legal_requested_size_and_reference_hashes(studio, codex_fake):
    folder, _, source = codex_fake
    from spriteforge.production.records import load_character
    image, _ = still_input(studio.root, load_character(studio.root))
    adapter = get_image_provider("gpt-image", load_tools(studio.root))
    reference = source.read_bytes()
    job = ImageJob("Only change expression", "", image, references=[reference], size=(512, 512))
    assert adapter.output_size(image, job.size) == "816x816"
    assert adapter.edit(job) == reference
    [call] = codex_calls(folder)
    assert [entry["sha256"] for entry in call["images"]] == [hashlib.sha256(image).hexdigest(), hashlib.sha256(reference).hexdigest()]
    assert "816x816" in call["prompt"]
    with pytest.raises(ValueError):
        adapter.preview(ImageJob("x", "", image, size=(5000, 1000)))
    assert len(codex_calls(folder)) == 1


@pytest.mark.parametrize("value", [True, "100", {}, math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("coordinate", ["top", "center"])
def test_pose_expected_rejects_nonfinite_or_nonnumeric_geometry_before_writing(studio, value, coordinate):
    before = load_owner(studio.root, "pose", "smile")
    with pytest.raises(ValueError, match="finite"):
        set_expected(studio.root, "smile", value if coordinate == "top" else None, value if coordinate == "center" else None)
    assert load_owner(studio.root, "pose", "smile") == before

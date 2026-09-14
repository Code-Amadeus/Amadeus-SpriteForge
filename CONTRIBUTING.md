# Contributing

Start with the generated examples before importing personal assets. Python 3.12
and Node 22 are the reference development environment. This is a local, single-user
editor, not an internet-facing service.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[qa,dev]"
npm ci
npx playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q
```

On Windows PowerShell, point browser tests at this interpreter:

```powershell
$env:SPRITEFORGE_PYTHON = (Resolve-Path .venv/Scripts/python.exe).Path
npm run test:ui
node tools/ktx_smoke.cjs
```

On Linux/macOS:

```sh
export SPRITEFORGE_PYTHON="$PWD/.venv/bin/python"
npm run test:ui
node tools/ktx_smoke.cjs
```

For installed Microsoft Edge, set `BROWSER_CHANNEL=msedge`. Browser smoke tests
use temporary authoring workspaces and the checked-in geometric KTX2 example.

## Contracts to preserve

- The selected workspace owns authoring paths, clip variants and saved coordinates.
- A runtime package supplies topology, indexed textures and playback metadata.
- The optional layout companion supplies only coordinates, matched by node ID and
  label. Never replace a creator's saved layout with inferred coordinates.
- Preview and export share the frame resolver. No character-specific frame substitutions.
- Existing projects and export destinations are not overwritten. Invalid graph saves
  preserve the previous file; incomplete exports are not published as valid packages.
- Runtime packages remain independent of Amadeus services, source PNGs and editor paths.

Use tests for observable behavior and both sides of these boundaries. Image layout
changes also need a real browser check; passing Python tests alone is insufficient.

## Dependency and packaging changes

Browser decoder dependencies are checked in with licenses so users can view KTX2
offline. Run `python tools/revendor_pixi_basis_ktx2.py --check` when touching the
KTX2 vendor files. Preserve `tools/vendor_hashes.json` and upstream notices.

```powershell
python -m pip install build
python -m build
```

Install the wheel into a fresh virtual environment with `--no-deps`, then run a
KTX2 browser smoke test using that interpreter. The wheel contains runtime code,
web assets and licenses. Source archives additionally contain examples, schemas,
documentation and test tools. The demo generator is available in both distributions.

Changes to the Amadeus export contract need a real `toktx` export and a validation
through the main Amadeus loader. Clearly distinguish encoder-stub tests from real
media verification.

## Reporting issues

Include the command, OS/Python/browser versions, whether the input is an authoring
workspace or a runtime pack, and the error message. A small reproducible graph or
generated example is more useful than a large personal asset directory.

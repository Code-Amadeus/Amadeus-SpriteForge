# Self-contained examples

- `minimal/`: PNG authoring workspace. These are original geometric sprites generated
  by `spriteforge.demo`, with a five-edge graph and explicit clip playback settings.
- `runtime-minimal/`: the same nine frames encoded with KTX-Software 4.4.2 UASTC,
  exported through the standalone exporter. It is a valid Amadeus v1 character pack.

```powershell
spriteforge review --workspace examples/minimal
spriteforge review --workspace examples/runtime-minimal
```

The PNG workspace is editable. Use `spriteforge init workspace --demo` for a fresh
working copy. The runtime pack opens read-only and needs no PNGs or export tool.
Both examples are AGPL-3.0-only and contain no third-party character artwork.

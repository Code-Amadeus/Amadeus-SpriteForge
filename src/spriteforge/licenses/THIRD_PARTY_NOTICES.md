# Browser dependencies

These files are bundled so installed users can review KTX2 without network access.
Their upstream licenses are retained and are not replaced by the project license.

| Component | Pinned source | License evidence |
| --- | --- | --- |
| `pixi.min.js` | [PixiJS 7.4.3](https://github.com/pixijs/pixijs/tree/v7.4.3), npm `pixi.js@7.4.3` | `LICENSES/pixi-MIT.txt`; copyright Mathew Groves and Chad Engler |
| `pixi-basis-ktx2.global.js` | [pixi-basis-ktx2](https://github.com/Sparcks/pixi-basis-ktx2), npm 0.0.22 | `LICENSES/pixi-basis-ktx2-MIT.txt`; copyright Kristof Van Der Haeghen |
| `basis_transcoder.js`, `basis_transcoder.wasm` | Decoder assets from that pinned npm package | Package MIT notice and [Basis Universal Apache-2.0](https://github.com/BinomialLLC/basis_universal/blob/master/LICENSE), copied to `LICENSES/basis-universal-Apache-2.0.txt` |
| `litegraph.core.js` | [LiteGraph.js commit 0555a2f2a3df5d4657593c6d45eb192359888195](https://github.com/jagenjo/litegraph.js/tree/0555a2f2a3df5d4657593c6d45eb192359888195), package version 0.7.14, `build/litegraph.core.js` | `src/spriteforge/web/vendor/litegraph.LICENSE`; MIT, copyright Javi Agenjo 2013 |

`tools/revendor_pixi_basis_ktx2.py --check` verifies the generated shim and decoder
against a SHA-512-pinned npm archive and pinned esbuild version. Browser bundles
were copied from Amadeus, not a character pack. `tools/vendor_hashes.json` records
the delivered files.

KTX-Software (`toktx`) is separately installed for export. OpenCV/NumPy and
Playwright are optional/development dependencies, not bundled binaries.

LiteGraph is used only as the workflow canvas editor. Its core bundle contains no
bundled executable node registrations. SpriteForge constructs nodes from its fixed
host schema, stores its own workflow JSON, and runs workflows only through the host
API after explicit confirmation. Canvas parameters and copy/paste use SpriteForge
controls; the library's expression evaluator and persistent clipboard are not used.
The SHA-256 of the verbatim core is
`2e730357dc2a9d41b5b457c1f173b326ff49e6190d8f1e33ce18fbec527e7701`.

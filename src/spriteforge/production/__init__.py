"""Production pipeline: character contract, prompts, pose stills, clip takes, rendering and QA.

Invariants that the modules in this package share:

- Approved pose stills are the only geometric authority. Every clip endpoint is
  registered, and optionally locked, to the still of its pose, so two clips that
  meet at a pose share endpoint geometry by construction.
- Takes are immutable provenance records and are never deleted. A decision only
  changes which take an owner accepts or whether a take is rejected.
- Prompt text is versioned data. Takes snapshot the rendered text with its block
  versions, and unresolved placeholders never reach a paid provider.
"""

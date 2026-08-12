# AGENTS.md

## Cursor Cloud specific instructions

This repository is **documentation-only**. It contains the `README.md`, a `docs/`
folder of Markdown design docs, and `.gitignore`. As the `README.md` states, there
is **no product code yet** (status: "concept / validated brainstorm").

Practical implications for future agents:

- There is **nothing to install, build, lint, test, or run** — no package manifest
  (`package.json`, `requirements.txt`, `go.mod`, etc.), no build system, no test
  suite, no services, and no application entrypoint.
- The environment update script is intentionally empty. Do **not** add dependency
  installation, build, or service-start steps until real product code (with its own
  manifest/tooling) is introduced.
- Development work here is editing Markdown. Preview docs with any Markdown viewer;
  no toolchain is required.
- When product code is eventually added, revisit this file: install its dependencies
  in the update script and document how to run/lint/test the new service(s) here.

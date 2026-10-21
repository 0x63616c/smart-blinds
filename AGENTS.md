# Smart Blinds

Hardware designs written in [atopile](https://atopile.io) (`.ato` files under `hw/`), built to KiCad layouts and fabricated at JLCPCB.

## Current product authority

Read `docs/brief.md`, `docs/measurements.json` and `docs/status.md` before design work.
Build a fresh integrated smart-blinds system for seven installations plus a spare. Archived designs
are evidence only; their locked architecture, part choices and validation claims are not authoritative.
Preserve inherited PD12V6 boards as labelled references. They are not battery chargers.

Group percentages represent a shared physical bottom-edge height, not each blind's own fraction.
Compare at least three complete enclosure layouts before freezing the PCB outline. Treat unmeasured
motor/holder geometry and electrical limits as provisional. Distinguish simulated, inspected and
physically tested results. No purchasing/fabrication without owner authorization.

Update source-generated previews and progress as sources change. Keep secrets out of the repository.
The owner permits subagents for alternative designs, comparisons, implementation and review.

## Native CAD automation

After a confirmed macOS KiCad embedded-Python crash on 20 October 2026, run
local automated KiCad Python, DRC, export and rendering through `tools/kicad-run`
in the isolated Linux environment. Existing isolated Linux CI jobs may run their
installed Linux KiCad directly. Do not launch the macOS embedded Python or
silently fall back to host KiCad when the runner is unavailable. Pure file
parsing is fine. The owner's interactive KiCad editor remains available.
Keep trial changes under `work/`; the runner must not overwrite canonical
designs during a study. Preserve a failed job's log and investigate before
rerunning it. Never change macOS crash-reporting settings to hide failures.

Visual PCB reviews must follow `docs/electrical/routing-style.md`, including
repeated inspection of actual rendered geometry and model alignment.

## Skills

Skills live in `.agents/skills/<name>/SKILL.md` (vendor-neutral Agent Skills format). `.claude/skills` and `.cursor/skills` are symlinks to that folder, so edit the originals in `.agents/skills` only. Load the relevant skill before starting work:

- `ato-language` — writing or reviewing `.ato` syntax, interfaces, parameters, design patterns
- `board-design` — composing packages into a board, connectors, power rails
- `build-and-test` — `ato build`, validation, build errors, sourcing parts from JLCPCB
- `creating-packages` — adding a new IC, component, or subcircuit
- `design-review` — reviewing a package or board before building or committing
- `layout-relinking` — renaming components that already have PCB placements
- `lsp` — hover, diagnostics, go-to-definition via the atopile LSP MCP server
- `trade-study` — comparing options when a design decision has real trade-offs

## Tooling

- The `lsp`, `ato-language`, and `design-review` skills use an MCP server registered as `atopile-lsp` (atopile LSP bridged over MCP). Register it in your agent's MCP config (`.mcp.json` for Claude Code, `~/.codex/config.toml` for Codex, `.cursor/mcp.json` for Cursor).
- Run `ato <command> --help` for CLI flags.

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

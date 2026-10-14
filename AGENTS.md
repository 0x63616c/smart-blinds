# e8s

Hardware designs written in [atopile](https://atopile.io) (`.ato` files under `hw/`), built to KiCad layouts and fabricated at JLCPCB.

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

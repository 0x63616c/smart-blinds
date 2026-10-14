---
name: lsp
description: Use when working with .ato files and you need semantic code intelligence — hover info, diagnostics, go-to-definition, find-references, or symbol inspection. Triggers on questions like "what type is this", "what members does X have", "where is X defined", "what uses Y", checking for parse errors, or understanding atopile module/interface signatures.
---

# Atopile LSP via MCP

The atopile LSP (`ato lsp start`) can be bridged to MCP (e.g. via [mcpls](https://github.com/bug-ops/mcpls)). This gives you semantic access to `.ato` files beyond what grep/read can provide.

Tools below are written as `atopile-lsp: <tool>`, meaning the `<tool>` tool on the MCP server registered as `atopile-lsp`. Each agent exposes MCP tools under its own naming scheme (Claude Code: `mcp__atopile-lsp__<tool>`; Codex and Cursor: the plain tool name under the server), so call whichever form your agent shows for that server. If the server is registered under a different name, substitute it.

## When to Use

- **Understanding a symbol** — hover gives type, members, docs, and usage examples
- **Checking for errors** — diagnostics surfaces parse errors and warnings after edits
- **Navigating code** — definition jumps to where a symbol is declared; references finds all usages
- **Formatting** — format_document applies language-specific formatting rules

Prefer these tools over grep when you need type information, interface members, or documentation.

## Working Tools

All position params are 1-indexed (as shown in editors).

| Tool | What it does | Key params |
|------|-------------|------------|
| `atopile-lsp: get_hover` | Type info, docs, members, usage examples | `file_path`, `line`, `character` |
| `atopile-lsp: get_diagnostics` | Parse errors/warnings for a file | `file_path` |
| `atopile-lsp: get_cached_diagnostics` | Same as above but from cache (faster) | `file_path` |
| `atopile-lsp: get_definition` | Jump to where a symbol is defined | `file_path`, `line`, `character` |
| `atopile-lsp: get_references` | Find all usages of a symbol | `file_path`, `line`, `character`, `include_declaration` |
| `atopile-lsp: format_document` | Format a file with language rules | `file_path` |

## Tools That May Return Empty

Depending on LSP version, some methods are not yet fully implemented and return no data:

| Tool | Notes |
|------|-------|
| `atopile-lsp: get_completions` | May run but return no items |
| `atopile-lsp: get_code_actions` | May run but return no actions |
| `atopile-lsp: get_document_symbols` | `textDocument/documentSymbol` may be unimplemented |
| `atopile-lsp: workspace_symbol_search` | `workspace/symbol` may be unimplemented |
| `atopile-lsp: prepare_call_hierarchy` | `textDocument/prepareCallHierarchy` may be unimplemented |

If a tool returns nothing, fall back to grep + `get_hover` on the located position.

## Usage Patterns

**Inspect a symbol** — use `get_hover` at the symbol's file position. Returns the type, full member list, and usage examples.

```
get_hover(file_path=".../some-driver.ato", line=36, character=8)
→ interface ElectricPower: voltage, max_current, hv, lv, gnd, vcc ...
```

**Check a file compiles** — use `get_diagnostics` after editing. Empty diagnostics = file parses clean.

**Find a definition** — use `get_definition` at a symbol reference. Returns the source file and line range.

**Find all usages** — use `get_references` at a symbol. Returns every location across the workspace.

**Explore an unfamiliar interface** — grep to find where it's used, then `get_hover` on that position.

## Common Mistakes

- **Wrong line/character** — 1-indexed, not 0-indexed
- **Skipping diagnostics after edits** — always verify `.ato` files parse cleanly

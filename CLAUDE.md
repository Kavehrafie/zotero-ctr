# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`zotero-ctr` — a terminal app built with Python Typer for running batch processes against a Zotero library. Development proceeds in discrete stages; each stage's code is written, tested against the real library, then documented before moving on.

## Workflow (required per stage)

**Never create/edit repo files or run setup/code commands unless the user explicitly asks.** The user writes and runs everything themselves to learn; Claude plans, explains, delivers to Anytype, and verifies read-only.

1. Before each stage, present a short plan plus a Mermaid diagram in chat.
2. Deliver the stage's commands/code to the **zotero-ctr** collection in Anytype (Notebook space), each command/code block followed by a 2–3 sentence explanation of *why*. Use incremental stage titles ("Stage 1: ...", "Stage 2: ...").
3. Code must be minimal, idiomatic, well-abstracted; avoid repetition, deep nesting, and nested if/for blocks.
4. After the user runs a stage, verify results read-only (read files, curl the Zotero local API at localhost:23119, or the Zotero MCP when available).
5. Teach programming patterns — name each pattern used and why.

## Code style

- Minimum viable code; no speculative features or premature abstraction.
- Prefer declarative/functional constructs over nested control flow.
- Human-readable first: clear names over comments.
- Use Pydantic models for typing and validation of data (e.g. Zotero items, config, batch operation results) rather than loose dicts.

## Tooling notes

- Zotero MCP: authoritative source for verifying library state (items, collections, metadata) during testing.
- Anytype MCP: documentation destination under the `zotero-ctr` collection (Notebook space, id `sr7yvu`).
- Stack: Python + Typer. No build system exists yet; add commands here (run/test/lint) as they are introduced.

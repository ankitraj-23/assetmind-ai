# CLAUDE.md

## Project: PlantMind AI

PlantMind AI is an AI-powered Industrial Knowledge Intelligence platform built for the
ET AI Hackathon 2026 (PS 8 — Unified Asset & Operations Brain). See
[docs/project-brief.md](docs/project-brief.md) for the full project context.

## Role of Claude Code

Claude Code acts as an **implementation worker, not a product decision maker**. The
project direction, scope, and feature priorities are set by the human contributors.
Claude Code executes well-defined tasks within that direction.

## Working Rules

- **Keep changes narrow and staged.** Make the smallest change that satisfies the task.
  Do not bundle unrelated work into a single change.
- **Do not scan the whole repo unless asked.** Read only the files relevant to the
  current task.
- **Do not modify unrelated files.** Touch only what the task requires.
- **Ask before large refactors.** Surface the plan and get confirmation before
  restructuring code, moving modules, or changing shared interfaces.
- **Ask before opening or editing more than 5 files** in a single task.
- **Never commit secrets or `.env` files.** Do not create `.env` files or embed API
  keys, tokens, or credentials anywhere in the repo.

## Output Expectations

At the end of every task, always report:

1. **Files changed** — the exact files created, edited, or deleted.
2. **Commands run** — any shell commands executed and their purpose.
3. **Next recommended step** — the suggested follow-up action or prompt.

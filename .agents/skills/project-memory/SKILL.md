---
name: project-memory
description: >-
  Maintains a living `memory.md` context and handoff file at the root of every project.
  Activate whenever starting work on a project, making meaningful codebase changes,
  completing a phase/task, or preparing context for another AI coding agent.
---

# Project Memory (`memory.md`) Workflow

`memory.md` is an **AI context and handoff file** stored at the project root (`./memory.md`). It is **not** human marketing documentation and **not** a copy of the codebase. Its goal is to let any new AI coding session or agent immediately understand the project without scanning the entire repository.

## Initial Setup (if `memory.md` does not exist)

1. Inspect the existing project structure and key files.
2. Create `memory.md` at the project root with the 12 required sections below.

## Required Sections in `memory.md`

1. **Project Overview**: What the project does, its purpose, and current stage.
2. **Architecture**: Important components, services, modules, data flow, and interactions.
3. **Tech Stack**: Frameworks, languages, libraries, databases, APIs, infrastructure, and tooling.
4. **Current State**: What is implemented and verified, what is partially implemented, and what works right now.
5. **Recent Changes**: Chronological summary of meaningful changes (what, why, affected files).
6. **Important Decisions**: Architectural and implementation decisions with rationale.
7. **Known Issues**: Bugs, limitations, technical debt, edge cases, and unresolved problems.
8. **Current Task**: What is actively being worked on and what remains.
9. **Next Steps**: Most logical next actions based on current project state.
10. **Important Files**: Key files/directories and their purpose (do not list every file).
11. **Environment & Configuration**: Env vars, scripts, commands, dependencies, setup details. **Never expose secrets, API keys, tokens, or private credentials.**
12. **Development Rules**: Project-specific conventions, constraints, and instructions for AI agents.

## Update Behavior (After Every Meaningful Code Change)

1. Review what changed.
2. Make targeted updates to the relevant sections of `memory.md` (do not rewrite the entire file unnecessarily).
3. Remove outdated information while preserving historical context that explains *why* the implementation exists.
4. Keep the file concise; never duplicate code.
5. Never claim something is implemented if it has not been verified.

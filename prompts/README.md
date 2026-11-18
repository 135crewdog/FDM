# Prompts and chat names (attempt 2)

The repository is the project's memory. A chat is only where one piece of work happens.

- **Chat name:** `FDM2 <number> <kind>: <topic>`, e.g. `FDM2 01 Work: JSBSim baseline`.
- **Kind:**
  - `Work`: Claude Code on the repository.
  - `Review`: an independent review.
  - `Plan`: a regular Claude chat, which cannot see the repository. Anything decided there only counts once it
    is written into the repository.
- **To start a session:** open a new chat of the right kind on `135crewdog/FDM` and paste the prompt file below
  its first line.

| Chat name | Prompt | Branch | Report |
|---|---|---|---|
| FDM2 00 Work: JSBSim research and baseline prompt (done) | (pasted in chat) | `main` | `RESEARCH.md` |
| **FDM2 01 Work: JSBSim baseline** (next) | `01-jsbsim-baseline.md` | `baseline/jsbsim` | `REPORT.md` on that branch |

Prompt 01 was rewritten on 2026-11-18 after the research session (00). Its old "ask me first" questions are
answered in `CLAUDE.md` (Decisions) and in the prompt itself.

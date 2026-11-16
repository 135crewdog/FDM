# Prompts and chat names

The repository is the project's memory. A chat is only where one piece of work happens. Any chat can be closed
or lost without losing anything, as long as its work was pushed.

## Chat names

Every chat for this project is named:

**`FDM <number> <kind>: <topic>`**

- **Number:** the session number. It is the same number as the report (`REPORT-04.md`), the prompt
  (`prompts/04-...md`) and the results (`results/04-*`).
- **Kind:**
  - `Work`: Claude Code on the repository. It changes code, runs tests and writes the report.
  - `Review`: the independent review (Codex). It checks a finished session.
  - `Plan`: a regular Claude chat for thinking and questions. It cannot see the repository. Anything decided there
    only counts once it is written into the repository.
- **Topic:** a few words.

The reports use "session" for these numbers. "Phase 2" in the reports means something else: the later
wing-strip physics work.

| Chat name | Prompt | Report |
|---|---|---|
| FDM 01 Work: evaluate the jsbsim-wasm package | (not in the repository) | `REPORT.md` |
| FDM 02 Work: our own WebAssembly build | (not in the repository) | `REPORT-02.md` |
| FDM 02 Review: build and integrator plan | `codex-review-02.md` | `REVIEW-codex-02.md` |
| FDM 03 Work: fixes, gates, candidate 1 | `03-fixes-and-integrator.md` | `REPORT-03.md` |
| FDM 04 Work: integrator decision | `04-integrator-decision.md` | `REPORT-04.md` |
| FDM 04 Review: integrator decision | `codex-review-04.md` | `REVIEW-codex-04.md` (verdict: not yet) |
| FDM 05 Work: ground model and default integrator | `05-ground-model-and-default.md` | `REPORT-05.md` (the default changed: midpoint, strut limits, 1200 Hz) |
| FDM 05 Review: ground model and default integrator | `codex-review-05.md` | `REVIEW-codex-05.md` (verdict: no, as shipped) |
| **FDM 06 Work: answer the review, first step of wing-strip forces** (next; needs `REVIEW-codex-05.md` in the repository) | `06-wing-strip-forces.md` | `REPORT-06.md` |

## How to use a prompt

1. Start a **new** chat of the right kind on `135crewdog/FDM`. Do not look for an old one.
2. Paste everything below the line in the prompt file.
3. The prompt's first instruction names the chat. If the chat cannot rename itself, it will ask you to.

## Rules for writing a prompt

- File name: `NN-<topic>.md` for work sessions, `codex-review-NN.md` for reviews.
- Put the chat name at the top of the file, and make "Name this chat ..." the first instruction below the line.
- Every work session ends by writing the prompt for the next chat, and adds a row to the table above.

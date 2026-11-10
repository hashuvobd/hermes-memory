# Coding-Agent Benchmark Boards

Which board answers which question, and how to read it. Fetch the live page; the
numbers here do not date well, the structure does.

| Board | Run by | What it measures | Read it when |
|---|---|---|---|
| **Terminal-Bench** (official, versioned, e.g. 4.x) | Snorkel AI with Harbor and the Laude Institute | A rolling set of real terminal tasks: write and debug code, configure environments, recover from failure, no GUI. Publishes resolution rate, tokens, and **cost per full run** per model+agent. | The default for agentic coding. Best single board for "which model should drive a coding agent". |
| **SWE-bench Verified** | Community dataset; independently run by Vals AI, Steel, Epoch | 500 human-validated GitHub issues, resolved by producing a patch that passes the repo's tests. Vals' independent runs use a minimal bash-only agent so the model, not the harness, is under test. | Rarely now. It saturated: the frontier cluster sits near the ceiling and boards have been archived because of it. Do not order models by it. |
| **Terminal-Bench (Vals AI run)** and similar independent re-runs | Vals AI | The same idea, their harness. Useful as a second opinion when the official board and a lab's own claim disagree. | When a vendor claim looks too good. |
| **FrontierCode** | Cognition; run in the open by Artificial Analysis / Epoch | Real-world coding tasks graded on whether a repository maintainer would merge the change. Whole-credit or partial (a band, not 0/1). | Judging merge-quality work rather than benchmark-shaped tasks. |
| **Artificial Analysis Coding Agent Index** | Artificial Analysis | A composite (e.g. FrontierCode + Terminal-Bench + a repo-understanding Q&A set) plus separate charts for wall time, tokens, per-task cost, safety refusals and reward hacking. | Comparing candidates across cost, latency and reliability at once, or when you need the reward-hacking and refusal columns. |
| **LMArena WebDev** (plus HTML / React / image sub-boards) | LMArena | Human pairwise preference on web and UI generation. An Elo-style rating, **not** a percentage; compare only within the board. | Front-end, layout, generated UI, "make it look right" work. |
| **LiveCodeBench / Aider polyglot style competitive-programming boards** | Various | Single-function or contest tasks, often with fill-in-middle. | Legacy only. Check the entry dates; a board with no new entries for months is not evidence about current models. |
| **Composite intelligence indexes** (Artificial Analysis Intelligence Index and similar) | Artificial Analysis and others | Nine or so evaluations averaged, with a stated weighting (coding, knowledge work, science). | A single headline number for general capability, knowing the domain weights behind it. |

## How to read any of them

- **Same harness, same effort, or it is not a comparison.** Boards publish the agent (Claude Code, Codex, mini-swe-agent, a custom harness) and the reasoning-effort setting. Mixed columns rank the harness as much as the model.
- **Per-run cost column is the honest price.** Token totals for a full evaluation run vary by an order of magnitude between models on identical tasks.
- **Percentages paste as-is; Elo does not.** Never put an Elo number in a table beside a resolution rate.
- **Version the board in the answer.** Verifier hardening between versions regrades the same submissions and moves every number; quote the version you read.
- **Margins are printed for a reason.** A score with a wide interval is not ahead of one with a narrow interval a point below it.
- **Open-weight rows need a memory figure.** Weights size at a practical quantization decides whether the entry is a real option for the user's machine; the parameter count alone does not.

## Report the read date

Say which boards you read and on what date. These pages change weekly, and a
recommendation is only as good as the day it was checked.

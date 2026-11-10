---
name: llm-model-selection
description: "Use when picking or comparing LLMs; verify live."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [models, benchmarks, comparison, providers, research]
---

# Model Selection, Verified Live

## When to Use

- "Which model is best for coding / writing / cheap bulk work?", "is X still good?", "what can I run locally?"
- You are about to name a model as a recommendation, or repeat a ranking from training.
- The user is choosing a model for a recurring job: cron fleets, subagents, a coding agent.

## Rule 0: never answer from recall

Training knowledge of model releases and leaderboards lags by a generation or more, and every process, price and version name moves monthly. Search first, answer second, and **state the date you read the boards**. If you already answered from recall before realising, correct it plainly rather than defending it.

## Procedure

1. **Search for the current leader on the board that matches the job**, not the general text board. See `references/benchmark-boards.md` for which board answers which question.
2. **Read primary sources**: the board's own page, or the organisation running it. Aggregator blogs are for discovery and for locating cost figures; never rank on one alone.
3. **Capture per candidate**: score, harness and effort setting, cost per full run or per task, release date, and for open weights the parameter count plus what a practical quantization costs in memory.
4. **Map to the user's constraints**: hosted or self-hosted, GPU memory, latency, price, and which providers are actually configured. Read the machine's hardware before recommending anything local.
5. **Answer as a small table plus scenario picks**, with the read date and the noise caveat.

## Pitfalls

- **Do not rank on a saturated benchmark.** Once the top cluster sits within a couple of points of the ceiling the board stops discriminating. Check whether it was archived or superseded and say so instead of quoting the ordering. See the reference for which boards are past this point.
- **Harness and effort move a score more than the model does.** Compare only entries run with the same harness and the same effort setting. A cheap small-model row with reasoning off beside a max-effort frontier row is a price signal, not a capability ranking.
- **Small gaps are noise.** Run-to-run variance on these boards is a few points; treat that as a tie and pick on price, latency or fit.
- **Cost per run beats price per token** for agentic work: the same task can consume an order of magnitude more tokens on one model than another, so headline per-million pricing misleads. Quote the per-run or per-task cost when the board publishes it.
- **For open weights, check the file size, not the parameter count.** A model can lead the board and still need multiple high-memory servers; say that plainly rather than listing it as an option on a 4 GB laptop GPU.
- **Never recommend a model the user's provider does not serve.** Check the configured providers or API endpoint first.
- **Separate capability from availability**: a model can top a board and still be unreachable in the user's region, tier or plan. Flag that rather than letting them discover it.

## Output shape

1. One line on what changed since your training, so the user knows the answer is fresh.
2. Table: model, score, cost, one-clause note. Sorted by score; name the harness when the table mixes them.
3. Three or four scenario picks: best quality, best value, best for long-horizon work, and the local option (or an explicit "nothing on this machine makes sense for this").
4. The date read, and the note that a two-point gap is not a reason to switch.

Keep the whole answer short. The user wants a pick and a reason to trust it, not a survey.

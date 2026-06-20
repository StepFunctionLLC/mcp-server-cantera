# Documentation contract for coding agents

This repository's public documentation is generated automatically by the **Step Function
documentation agent** ([Documentation-Agent](https://github.com/StepFunctionLLC/Documentation-Agent)),
which reads this repo and maintains a page on the centralized Sphinx + MyST site
(`https://coot.tail28751.ts.net/`). It builds the page in this structure:

> **Overview** (intent) · **Background & Theory** · **Architecture** (with a diagram) ·
> **Usage** · **API Reference** (concise) · **Configuration** · **Notes**

The docs are **professional engineering documentation**: they lead with the *theory*, the
*architecture*, and the *design logic* — the API listing is a brief orientation, not the
substance. The agent is accurate-by-design: **it documents only what this repo actually
states, and it will not invent the intent or the theory.** So when you change code here, keep
the source material below current — otherwise the generated docs go stale or omit context.

## What to maintain (so the docs are good)

- **Intent — in the README's opening / Overview.** One short statement of what this repo is
  and the problem it solves. Update it when the purpose shifts.
- **Background & Theory — write it down; it cannot be derived from code.** Keep a section
  (in the README, or a `THEORY.md` / `DESIGN.md`) describing the scientific / mathematical /
  engineering basis: the methods, models, governing equations, assumptions, and approach the
  code implements, with references/citations where relevant. **This is the highest-leverage
  thing to maintain** — if it isn't written here, it won't appear in the docs. Update it
  whenever you change the *method*, not just the code.
- **Architecture & design rationale — write down the *why*.** In the README or a
  `DESIGN.md`/`ARCHITECTURE.md`, describe the major components and their responsibilities, how
  data/control flows between them, and the key design decisions and trade-offs. The agent
  draws the architecture diagram and the supporting-logic discussion from the code *and* this
  prose — explaining intent and trade-offs that code alone can't convey makes the docs far
  stronger.
- **API details — in accurate docstrings.** Public functions, classes, and commands should
  have docstrings with correct signatures, parameters, returns, and units. The agent distills
  these into a *concise* API Reference (key entry points only); private/internal names
  (leading underscore, tests, build glue) are intentionally left out.
- **Usage — minimal, runnable examples** in the README (install + the primary workflow). Keep
  them working.
- **Configuration — document** environment variables, CLI flags, and config files.

## Guidance

- Treat the README + docstrings + theory notes as the **source of truth** the docs are built
  from; keep them in sync with the code in the same change.
- If a public-surface change has no doc-relevant effect (refactor, tests, formatting), no doc
  action is needed — the agent will detect that and skip it.
- If the intent or theory is genuinely missing, the docs will be thin and the agent may open
  an issue here requesting it. Prefer to write it proactively.

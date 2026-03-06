# gaas-bot Decisions Log

Architectural decisions for gaas-bot, recorded when they're made. Each entry captures the context and constraints at the time. If constraints change, update or retire the decision.

---

## 001: Single structured output for audit findings (2026-03-05)

**Context**: Audit commands (docs, refactor, tests) need to produce GitHub issues from their findings. Three approaches were considered:

- **Option A (chosen)**: Single Claude agent call with `output_model=AuditReport` returning a list of findings. Python iterates findings and creates issues programmatically.
- **Option B**: Two-phase agent — Phase 1 explores freely with tools, Phase 2 receives Phase 1's text and returns structured output. Decouples exploration from formatting.
- **Option C**: Claude writes `to_review/*.md` files with YAML frontmatter, Python parses them post-hoc.

**Decision**: Option A — single structured output.

**Rationale**: Audit commands are read-only exploration. Claude doesn't need Write tool access if it returns structured output, which is a trust improvement (the agent literally can't modify the worktree). One agent call, one structured output, one deterministic creation loop — fewest moving parts, easiest to test, most auditable. This aligns with the project principle "log what the agent does, don't ask it what it did" — structured output is a schema-enforced contract, not a hope that the LLM wrote valid files.

**Assumption**: This decision assumes Claude can produce quality structured output for audit-sized reports (up to 10 findings with detailed markdown bodies). If structured output quality degrades — truncated findings, malformed JSON, or the model struggling with the schema complexity — Option B (two-phase: explore then structure) is the fallback. The two-phase approach lets Claude explore freely in Phase 1 and then format in Phase 2 as a pure structuring task, which is more resilient to output quality issues.

**Revisit when**: Structured output from the agent SDK proves unreliable for reports of this size, or audit prompts need to use tools like Write during exploration that conflict with structured output mode.

---

## 002: Multi-stage pipeline for PR review (2026-03-06)

**Context**: The `review` command needs to analyze a PR diff, generate findings, and post a formatted comment. Three pipeline architectures were considered:

- **Option A**: Single-stage — one agent call gets the diff, explores the code, and returns findings. Same pattern as audit. Fastest to ship, lowest token cost.
- **Option B (chosen)**: Three-stage with session continuity — analyze (build understanding), review (generate findings), draft (format comment). Each stage resumes the previous session. ~3x the token cost.
- **Option C**: Single-stage with a `--depth` flag varying prompt templates and max turns. Same code path as A but with three prompt variants.

**Decision**: Option B — three-stage pipeline with session continuity.

**Rationale**: Code reviews benefit from separating understanding from judgment. When analysis and critique happen in one pass, the agent tends to start generating findings before it has full context, leading to shallow or incorrect observations. The three-stage approach forces the agent to build a complete picture of what changed and what's at risk (analyze), then critique with that context loaded (review), then format without the cognitive load of analysis (draft). Session continuity means no context is lost between stages. The extra token cost is acceptable because reviews are only triggered for non-trivial PRs where thoroughness matters.

**Assumption**: The session continuity mechanism (`resume:<stage>`) reliably preserves the agent's working memory across stages. If the agent SDK's session resumption degrades or introduces latency problems, Option A with a more detailed single prompt would be the fallback.

**Revisit when**: Session resumption proves unreliable, or the three-stage cost becomes prohibitive for the volume of PRs being reviewed. Option C's `--depth` flag could be layered on top of either A or B if variable thoroughness becomes needed.

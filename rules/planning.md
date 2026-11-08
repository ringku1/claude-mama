# Planning and decisions

## Done criteria first

Write criteria before steps. Each must be checkable by a command, a test, or a cited source — "works well" isn't a criterion; "filtering by price returns only matching courses (test X)" is. Research criteria: "question answered with cited evidence".

## Steps

- **Walking skeleton first**: the first build step is a thin end-to-end slice (one endpoint → one screen), not a full layer. It exposes design mistakes while they're cheap.
- **Size**: one step = one dev + test cycle. Too small wastes agent setup → batch it. Too large fails slowly → split it.
- **Kinds**: build · fix · research · document · decide · release (see `rules/loop.md`).
- **Ownership**: each step lists the files/dirs it owns. Parallel steps must not overlap — overlap means add a dependency.
- **Verify**: each step names its narrowest proof, from `profile.md` commands. Mark slow verifies (full build, e2e).
- **Critical path**: order so the longest dependency chain and slow-verify steps start earliest.
- **Confidence**: H/M/L per step. L steps get research or a question before building.
- **Deliverables**: each is a `document` step with its output path.
- **Budget**: size S (≤300k tokens) / M (≤1M) / L (set a number); record in plan header. Reference from real runs: a 3-step UI polish goal with one checker ≈ 150k; a 3-step toy build ≈ 70k; a cited research guide ≈ 110k; each checker agent ≈ 40k. Prefer `lessons.md` numbers from this repo when they exist.
- **Time estimates** are in agent minutes, not human hours — a small build step typically takes 2-5 min, a checker 1-2 min. Calibrate from `lessons.md` (actual vs estimate) and `patterns.md`. ETAs in the overview come from these, so wrong estimates mislead the user.

## Validate before showing

Check, fix, then present:
- [ ] Every done criterion maps to ≥1 step
- [ ] No dependency cycles; no ownership overlap between parallel steps
- [ ] Every step has a verify that actually exercises its criterion
- [ ] Steps are right-sized; skeleton first; critical path early
- [ ] No step depends on an unconfirmed `assumed` decision
- [ ] Precedent followed, or a decision says why not
- [ ] Nothing in scope that the goal didn't ask for (park it)

Show the plan as ONE compact table — `step · kind · depends on · verify` — plus the criteria, and wait for approval.

## Decision rules

Record every decision as a `D` line in `log.md`: question, choice, why, evidence, tag.

- **Evidence tags**: `verified` (read the code / ran it), `inferred`, `assumed`, `user`. Prefer verified; never build on unconfirmed assumed.
- **Precedent**: find how this repo already solved the same kind of problem and follow it. Deviating needs a stated reason.
- **Reversibility**: code on an unmerged branch is reversible — including the behaviour of new functions. Decide, log, flag for review in overview. One-way = things that reach beyond this branch or are costly to undo: database schema/migrations, contracts other code or teams already consume, new dependencies, data deletion, anything outward-facing. Those → ask. "New dependency" includes plugins and companions of one the user already approved (e.g. `remark-gfm` next to an approved `react-markdown`) — ask in one line before installing; don't fold it into the earlier approval.
- **Options**: for non-trivial choices weigh 2-3 options against the goal's criteria (risk, reversibility, fit with repo rules, effort) and pick one. No exhaustive surveys.
- **Second opinion**: only for a decision that shapes the whole plan — one agent argues against your recommendation. Rare; it costs tokens.
- **Consistency**: check decisions in force (`grep '^D' log.md`) before deciding. A new decision that conflicts with an old one must explicitly supersede it (`Dn supersedes Dm`).

## Milestones

A milestone is a point where something works end to end. Mark its last step with ★ in notes: one ★ per ~3-5 steps in larger goals; small goals may have none. Never add steps just to create a milestone — the pre-delivery checkpoint (`rules/loop.md`) always exists anyway.

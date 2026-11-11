# Planning and decisions

## Done criteria first

Write criteria before steps. Each must be checkable by a command, a test, or a cited source — "works well" isn't a criterion; "filtering by price returns only matching courses (test X)" is. Research criteria: "question answered with cited evidence".

## Steps

- **Walking skeleton first**: the first build step is a thin end-to-end slice (one endpoint → one screen), not a full layer. It exposes design mistakes while they're cheap.
- **Size**: one step = one dev + test cycle. Too small wastes agent setup → batch it. Too large fails slowly → split it.
- **Kinds**: build · fix · research · document · decide · release (see `rules/loop.md`).
- **Width — plan for parallel work.** The user wants speed, so split the work into as many independent steps as it allows, each owning a disjoint area: per endpoint or module on the API, per screen or component on the web, tests, docs, deliverables. Put a thin **contract step** first when parallel steps share an interface (shared types, the API shape, the migration) — the lead writes it in minutes and every step after it runs at once. Real run: two web agents on disjoint files, after the lead wrote the shared types, halved wall time with no conflicts. Tests for a criterion can be written by a test agent while the build runs. A chain is serial only for a real dependency, never for convenience.
- **Ownership**: each step lists the files/dirs it owns. Parallel steps must not overlap — split the files differently or, if they truly must, add a dependency. Generated files (OpenAPI spec, route tree, i18n output) belong to one step, or the lead regenerates once after the parallel steps land.
- **Verify**: each step names its narrowest proof, from `profile.md` commands. Mark slow verifies (full build, e2e).
- **Critical path**: order so the longest dependency chain and slow-verify steps start earliest. `plan-set.py` prints the critical path, the sum and how many steps can run at once — a wide plan has a critical path well under the sum.
- **Confidence**: H/M/L per step. L steps get research or a question before building.
- **Deliverables**: each is a `document` step with its output path.
- **Code review goals**: use the built-in `/code-review` skill (its effort level = the depth the user picked) for the review step, not hand-briefed reviewer agents — on a large feature branch it found 10 real rule breaks that a 4-reviewer custom review (1.06M tokens) had missed. Add custom reviewers only for an area it doesn't cover (e.g. design match).
- **Budget**: size S (≤300k tokens) / M (≤1M) / L with a number (`L 1.5M`); record in plan header. Measured real spend so far: slug switch build 457k, 4-reviewer branch review + 14 fixes 1.06M, full test sweep 845k, 26 bug fixes 556k, /code-review high + 10 fixes 679k, report artifact 23-39k, API + web page with /code-review and fixes 1.16M, merging main ~400 commits behind (29 conflicts) + an API+web feature + a scope change ≈ 4.2M, a small API+web add-on to a module already built ≈ 280k — size from these, not from feel. Reference from real runs: a 3-step UI polish goal with one checker ≈ 150k; a 3-step toy build ≈ 70k; a cited research guide ≈ 110k; each checker agent ≈ 40k; a reviewer agent over a large branch diff (~80 files) ≈ 150-170k each (4 reviewers ≈ 655k), so a multi-reviewer review is M at least, L if fixes follow. Prefer `lessons.md` numbers from this repo when they exist.
- **Time estimates** are in agent minutes, not human hours — a small build step typically takes 2-5 min, a release step 1-2 min, a checker 1-2 min, a reviewer agent on a big diff 5-9 min. A goal takes about its **critical path** (the longest chain of dependent steps), never the sum: parallel steps overlap, and sums ran 3-4× over. `plan-set.py` prints it after every step change (`estimate: critical path … · left …`). Real runs took a median ⅔ of the critical path (43→29, 39→34, 47→35, 105→50, 110→56, 155→46 min); runs that went over were API + web with a code review (88→108) and a merge of a main far behind (315→375 active) — size those at the full critical path or more. Wall time across a night or a long break isn't work: close-check counts gaps over 2h as idle. The estimated finish shown to the user is now + the critical path left, calibrated. Calibrate from `lessons.md` (actual vs critical path) and `patterns.md`; wrong estimates mislead the user.

## Validate before showing

Check, fix, then present:
- [ ] Every done criterion maps to ≥1 step
- [ ] Every `case:` from research is covered — by a criterion or a step's verify, a logged decision, or a parked line
- [ ] No dependency cycles; no ownership overlap between parallel steps
- [ ] Every step has a verify that actually exercises its criterion
- [ ] Steps are right-sized; skeleton first; critical path early
- [ ] As wide as the work allows: every dependency is real; a long chain that could split is split; a contract step unblocks parallel work
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

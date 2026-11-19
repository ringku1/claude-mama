# Planning and decisions

## Done criteria first

Criteria come before steps, each checkable by a command, test or cited source: not "works well" but "filtering by price returns only matching courses (test X)". Research: "question answered with cited evidence".

## Steps

- **Walking skeleton first**: the first build step is a thin end-to-end slice (one endpoint → one screen), not a full layer: design mistakes show while cheap.
- **Size**: one step = one dev + test cycle. Too small wastes agent setup → batch. Too large fails slowly → split.
- **Kinds**: build · fix · research · document · decide · release (`rules/loop.md`).
- **Width — plan for parallel work.** As many independent steps as possible, each owning a disjoint area: per API endpoint or module, per web screen or component, tests, docs, deliverables. Parallel steps sharing an interface (types, API shape, migration) get a thin **contract step** first, written by the lead in minutes. A test agent can write a criterion's tests during the build. A chain is serial only for a real dependency.
- **Ownership**: each step lists the files/dirs it owns. Parallel steps never overlap: re-split the files or, if unavoidable, add a dependency. Generated files (OpenAPI spec, route tree, i18n output) belong to one step, or the lead regenerates them once after parallel steps land.
- **Verify**: each step names its narrowest proof, from `profile.md` commands. Mark slow verifies (full build, e2e).
- **Critical path**: start the longest dependency chain and slow verifies earliest. `plan-set.py` prints the critical path, the sum and how many steps run at once; a wide plan's critical path is well under the sum.
- **Confidence**: H/M/L per step. L steps get research or a question before building.
- **Deliverables**: each is a `document` step with its output path.
- **Code review goals**: the review step uses the built-in `/code-review` skill (effort level = the depth the user picked), not hand-briefed reviewer agents; custom reviewers only for an area it misses (e.g. design match).
- **Budget**: S (≤300k tokens) / M (≤1M) / L with a number and unit (`L <n>k|M`, e.g. `L 800k`, `L 1.5M`), set at approval from the printed **tokens likely** (`budget=M`, `budget='L 1.5M'`) with `auto-raise=1.5x` (`rules/loop.md` → Budget). Header form: `~<n>k / S|M|L <n>k|M`; the approved size stays as `approved:`. Size from measured spend, not feel: slug switch build 457k; 4-reviewer branch review + 14 fixes 1.06M; full test sweep 845k; 26 bug fixes 556k; /code-review high + 10 fixes 679k; report artifact 23-39k; API + web page with /code-review and fixes 1.16M; merging main ~400 commits behind (29 conflicts) + an API+web feature + a scope change ≈ 4.2M; small API+web add-on to a built module ≈ 280k; 3-step UI polish with one checker ≈ 150k; 3-step toy build ≈ 70k; cited research guide ≈ 110k; checker agent ≈ 40k; reviewer agent over a large diff (~80 files) ≈ 150-170k (4 ≈ 655k), so a multi-reviewer review is M at least, L if fixes follow. This repo's `lessons.md` numbers win. `plan-set.py` and `estimate.py` print **tokens likely** (steps × median tokens per step of the last 10 goals) and flag a smaller size; cover it (picked sizes ran half to 4× actual use).
- **Time estimates** are agent minutes: small build step 2-5 min, release or checker 1-2 min, reviewer agent on a big diff 5-9 min. A goal takes about its **critical path**, never the sum (sums ran 3-4× over). `plan-set.py` prints it after every step change (`estimate: critical path … · left …`); it and `estimate.py` print the **likely** time: critical path × median actual / critical path of the last 10 goals (this repo's `lessons.md`, then `patterns.md`). Tell the user the likely time; estimated finish = now + likely time left. Merging a far-behind main, or API + web with a code review: full critical path or more. Close-check counts gaps over 2h as idle.

## Validate before showing

Check, fix, then present:
- [ ] Every done criterion maps to ≥1 step
- [ ] Every confirmed playback example (`rules/questions.md`) is (part of) a criterion, proven by a test or check the user can repeat
- [ ] Code goals end with one `hunt` step (deps: every build and fix step; est 10–15m per capped round; the release step depends on it) — `rules/loop.md` → Bug hunt
- [ ] The migration and every database-touching step follow the agreed design (`D … db:` lines) — nothing more, nothing different
- [ ] Every `case:` from research is covered by a criterion, a step's verify, a logged decision or a parked line
- [ ] No dependency cycles; no ownership overlap between parallel steps
- [ ] Every verify exercises its criterion
- [ ] Steps right-sized; skeleton first; critical path early
- [ ] As wide as the work allows: every dependency real; a splittable long chain split; a contract step unblocks parallel work
- [ ] No step depends on an unconfirmed `assumed` decision
- [ ] Precedent followed, or a decision says why not
- [ ] Nothing in scope the goal didn't ask for (park it)

## Decision rules

Record every decision as a `D` line in `log.md`: question, choice, why, evidence, tag.

- **Evidence tags**: `verified` (read the code / ran it), `inferred`, `assumed`, `user`. Prefer verified.
- **Precedent**: follow how this repo already solves the same kind of problem.
- **Reversibility**: unmerged-branch code, including new functions' behaviour, is reversible: decide, log, flag for review in overview. One-way (reaches beyond this branch or costly to undo) → ask: database schema/migrations (any change to the agreed design goes back to the user, `rules/questions.md` → Database changes), contracts other code or teams already consume, new dependencies, data deletion, anything outward-facing. A plugin or companion of an approved dependency (e.g. `remark-gfm` next to an approved `react-markdown`) is a new dependency: ask in one line before installing, never folded into the earlier approval.
- **Options**: non-trivial choices weigh 2-3 options against the goal's criteria (risk, reversibility, fit with repo rules, effort) and pick one; no exhaustive surveys.
- **Second opinion**: only for a decision shaping the whole plan, one agent argues against your recommendation. Rare; it costs tokens.
- **Consistency**: check decisions in force (`grep '^D' log.md`) first. A new decision conflicting with an old one explicitly supersedes it (`Dn supersedes Dm`).

## Milestones

A milestone is where something works end to end. Mark its last step ★ in notes: one per ~3-5 steps in larger goals; small goals may have none. Never add steps just to make one; the pre-delivery checkpoint (`rules/loop.md`) always exists. A finished ★ step refreshes the overview's prose; other steps only move its Status line.

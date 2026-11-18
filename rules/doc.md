# Explaining a goal's work (`/mama doc`)

Read for `/mama doc [<slug>]`: one page that explains everything a goal built or found, written so a new teammate understands it in one read. Works on open and closed goals, from any session.

- **Which goal:** as in `ask` (`rules/ask-test.md`), named in the first line of the reply.
- **Read-only:** no edits to the goal's code, `plan.md`, `log.md` or `overview.md`. The page goes to `<store>/<slug>/doc.html` and its link to `doc.url`, both through `scripts/doc-save.py`; nothing else is written. If the work turns out wrong or missing, say so and offer `/mama change <slug> …` (open goal) or a new goal (closed one).

## 1. Gather the record

Cheapest first: `overview.md` → `plan.md` (criteria and evidence, steps and notes, Parked) → `log.md` (`^D` decisions with reasons, `^F` findings, `db:` lines, last `hunt` rounds) → `tests.md` → the code. Code: the goal's worktree if it exists, else the branch (`git -C <main checkout> diff --stat <base>...<branch>`, files via `git show <branch>:<path>`). For a research goal, the "code" is what it studied, and its findings are the content.

## 2. Research in parallel

Up to 10 changed files in one area: do it inline. Otherwise one read-only agent per lens, all in one message (`rules/agents.md` for model and limits). Each gets the goal line, the worktree or branch, the changed-file list and the relevant `D`/`F` lines, and returns plain notes (≤ ~600 words) with a `file:line` for every claim:

- **Flow:** every way the work starts (route, screen action, command, job, event), then each function or method the goal added or changed, in call order. For each one: what it takes, what it does and why, what it returns, what it calls, which errors it handles.
- **Data:** every table, view and type the goal created or changed. For each column: type, whether it can be empty, default, key, what it holds, why (from `D … db:`), and who reads or writes it. Also the indexes and constraints, the migration, and what happened to existing rows. Say "no database change" when there is none.
- **Depends on / used by:** the modules, packages, services, config and env var *names* (never values), and other branches or goals this work relies on: how it uses each one, and what breaks if that thing changes. Then what relies on this work.
- **Left to do:**
  - open criteria and unfinished or blocked steps;
  - Parked ideas;
  - known issues and follow-ups from the bug hunts and the final report;
  - delivery state: pushed or not, PR open or merged (`gh`), merges still needed;
  - the tests the user hasn't run yet (`tests.md`).

Where the record and the code disagree, the code wins, and the page says so. What neither one shows is written as "not recorded", never guessed.

## 3. Write the page

Pick one small, concrete example that runs through the whole page (e.g. "Rina uploads `notes.pdf`, 2 MB, to Course 12") and reuse its values in the flow, function and data sections. Sections, in this order:

1. **At a glance:** what it does, in 2–3 sentences; the example as a short story; status and progress.
2. **The whole flow:** a diagram from trigger to result (a sequence or flowchart), then a numbered walk-through that follows the example values through each step.
3. **Each part:** grouped by module or screen. For each function or method: what it does and why, the example's input and output, what it calls, and what can go wrong. Names in `monospace`, with the `file:line` in small text. Add a snippet of a few lines only when it makes an idea clearer.
4. **Data:** an entity-relationship diagram, then one table per database table with these columns: column, type, can be empty, default, meaning, why. Add an example row using the example's values, the indexes and constraints, and what the migration did to existing rows.
5. **Why it's built this way:** each user decision with its reason and the rejected alternative.
6. **Depends on / used by:** a diagram, then a table with the columns: thing, how it's used, what breaks if it changes.
7. **What's left:** each item, why it matters, and the next action for it.
8. **Words used:** a one-line definition of each term the page uses.

Plain words throughout:
- short sentences;
- every technical term explained the first time it appears;
- no plan or log IDs;
- no secrets, keys, env values or customer data.

The page is one self-contained HTML file with inline CSS and light and dark themes. It must also work opened straight from disk, so its diagrams are inline SVG, or Mermaid with its own `<script src="https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js">` and the call that starts it, never relying on a viewer to draw them. If the Artifact tool is available, follow its page contract first: its quickstart or design guidance. Big goals: one agent writes the page from the lens notes (they go into its brief, or into a scratch file it reads), so you don't hold the HTML.

## 4. Publish and reply

- Write the page to a scratch file (the session's scratchpad, else a temp folder): file tools treat `.claude/` as sensitive. Save it with `bash ${CLAUDE_SKILL_DIR}/scripts/py ${CLAUDE_SKILL_DIR}/scripts/doc-save.py <store>/<slug> <scratch file>`. The script refuses a page that isn't whole, or Mermaid diagrams without their script; fix the page and save again. It prints the link on record (`doc.url: …`).
- **Artifact tool available:** publish the saved `doc.html` as a private page.
  - A link is on record: pass it as `url` to update the same page.
  - First publish: record the link with `doc-save.py <store>/<slug> --url <link>`.
- **No Artifact tool, or publishing declined:** give the path of `doc.html` to open in a browser.
- **Reply** with the link or path, one line on what the page covers, and what the record doesn't show.

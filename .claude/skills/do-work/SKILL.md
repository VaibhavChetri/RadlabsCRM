---
name: do-work
description: "Execute a unit of work end-to-end: plan, implement, validate with tests, lint, and build, then commit. Use when user wants to do work, build a feature, fix a bug, or implement a phase from a plan."
---

# Do Work

Execute a complete unit of work: plan it, build it, validate it, commit it.

## Workflow

### 1. Understand the task

Read any referenced plan or PRD. Explore the codebase to understand the relevant files, patterns, and conventions. If the task is ambiguous, ask the user to clarify scope before proceeding.

### 2. Plan the implementation

If a plan already covers this work, follow it. Otherwise write a short plan before touching any code: what will change, in which files, and how you'll know it works.

### 3. Implement

**For backend code (Python)**: use red/green/refactor, one test at a time, tracer-bullet style.

*Note: If `pytest` is not yet configured in the backend, install it and create a minimal test setup first before writing the first failing test.*

1. **Red** — write ONE failing `pytest` test for the smallest vertical slice of behavior. Run it. Confirm it fails for the right reason.
2. **Green** — write the minimum Python code to make that test pass. Run it. Confirm it passes.
3. **Refactor** — clean up code and test while all tests stay green.
4. Repeat from step 1 for the next slice.

Rules:
- Never write several tests upfront. One test → pass → next test.
- First test = tracer bullet: the thinnest path end-to-end (e.g. API route → service call → DB → result). Later tests add edge cases and error paths.
- Do not write code that no failing test asks for.

**For frontend code (JavaScript / React)**: implement directly, no TDD.

### 4. Validate

Run all feedback loops and fix any issues. Repeat until every check passes cleanly.

- **Backend tests:** Run `pytest` in the backend directory.
- **Backend boot check:** Run `python -c "import main"` in the backend directory to confirm the app imports without syntax or startup errors.
- **Frontend lint & build:** Run `npm run lint` and `npm run build` in `frontend/`.

### 5. Commit

Once all validation checks pass, commit the work. This is the final step: the unit of work isn't done until it's committed.

Stage only the files from this unit of work, by name, never `git add .`. The working tree may hold unrelated changes that don't belong in this commit.

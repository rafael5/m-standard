# Build log

Chronological record of non-trivial issues encountered during
construction of `m-standard`. Entries follow the vista-meta `BL-NNN`
convention: short title, what we were doing, what went wrong (or what
required a non-obvious decision), how it was resolved.

Trivial fixes (typos, obvious renames, routine dependency bumps) do
not get an entry — they belong in commit messages, not here.

---

## BL-001 — Project bootstrapped from python template (2026-04-25)

**Phase:** A0 — repo skeleton.
**Context:** Copied `~/claude/templates/python` into the existing
`m-standard/` (which already held LICENSE and the spec draft), renamed
the package to `m_standard`, and rewrote the Makefile to use
`.venv/bin/` prefixes for every tool invocation.

**Why the Makefile rewrite:** the upstream template uses bare tool
names (`pytest`, `ruff`, `mypy`, `pre-commit`) which are hijacked by
the parent direnv's `VIRTUAL_ENV=/home/rafael/claude/.venv` and run
against the wrong packages. This is a known upstream-template bug
(captured in `~/claude/memory/feedback_python_template_bug.md`); fixed
locally on bootstrap.

**Outcome:** `make install` and `make test` run against this
project's `.venv/` as intended. No further action required for this
project; upstream template fix is tracked separately.

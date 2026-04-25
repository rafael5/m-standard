.PHONY: install hooks test test-lf watch lint format mypy cov check push pull \
        sources sources-anno sources-ydb serve-anno extract reconcile validate all clean

PYTHON     := .venv/bin/python
PYTEST     := .venv/bin/pytest
PTW        := .venv/bin/ptw
RUFF       := .venv/bin/ruff
MYPY       := .venv/bin/mypy
PRECOMMIT  := .venv/bin/pre-commit

# ----- standard project targets -----

install:
	uv sync --extra dev
	$(MAKE) hooks

hooks:
	$(PRECOMMIT) install --hook-type pre-commit --hook-type pre-push

test:
	$(PYTEST)

test-lf:
	$(PYTEST) --lf

watch:
	$(PTW) -- --tb=short

lint:
	$(RUFF) check src/ tests/

format:
	$(RUFF) format src/ tests/

mypy:
	$(MYPY) src/

cov:
	$(PYTEST) --cov --cov-report=term-missing

check: lint mypy cov

pull:
	git pull origin main

push: check
	git push origin main

# ----- m-standard pipeline (per spec §8) -----

# Acquire / refresh all three offline source replicas.
sources: sources-anno sources-ydb sources-iris sources-sac

sources-anno:
	$(PYTHON) -m m_standard.tools.crawl_anno

sources-ydb:
	bash tools/clone-ydb.sh

sources-iris:
	$(PYTHON) -m m_standard.tools.crawl_iris

sources-sac:
	bash tools/clone-sac.sh

# Serve the local AnnoStd mirror over http://localhost:8765
serve-anno:
	cd sources/anno/site && $(PYTHON) -m http.server 8765

extract:
	$(PYTHON) -m m_standard.tools.extract_anno
	$(PYTHON) -m m_standard.tools.extract_ydb
	$(PYTHON) -m m_standard.tools.extract_iris
	$(PYTHON) -m m_standard.tools.extract_sac

reconcile:
	$(PYTHON) -m m_standard.tools.reconcile

emit-json:
	$(PYTHON) -m m_standard.tools.emit_json

emit-grammar:
	$(PYTHON) -m m_standard.tools.emit_grammar

emit-pragmatic:
	$(PYTHON) -m m_standard.tools.emit_pragmatic_standard

emit-sac:
	$(PYTHON) -m m_standard.tools.emit_sac_compliance

emit: emit-json emit-grammar emit-pragmatic emit-sac

validate:
	$(PYTHON) -m m_standard.tools.validate

all: sources extract reconcile emit validate

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

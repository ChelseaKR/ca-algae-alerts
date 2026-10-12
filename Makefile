# Repository-root gate (CI-CD-STANDARD §1 and §9, CODE-QUALITY-STANDARD §2).
#
# The Python project lives in pipeline/ and the Swift package in
# ios/AlgaeCore/ (the same nested layout as Trout Truck). CI's `verify` job runs
# `make verify` and nothing else, so a green `make verify` locally is the
# same claim as a green `verify` check.
#
# Needs: uv >= 0.11, gitleaks 8.30.1, osv-scanner 2.x on PATH.
#
# No recipe pipes one command into another: macOS ships GNU Make 3.81, which
# ignores .SHELLFLAGS, so a pipe could hide a failing command.

PIPELINE := pipeline
UV_RUN := uv run --frozen
SEMGREP_VERSION := 1.166.0
TMP := $(shell mktemp -d 2>/dev/null || mktemp -d -t caalgae)

.PHONY: verify sync format lint typecheck test smoke build audit sast secrets hygiene

verify: sync format lint typecheck test smoke build audit sast secrets hygiene

sync:
	cd $(PIPELINE) && uv lock --check
	cd $(PIPELINE) && uv sync --frozen

format:
	cd $(PIPELINE) && $(UV_RUN) ruff format --check .
	cd $(PIPELINE) && $(UV_RUN) ruff format --check --config pyproject.toml ../scripts

lint:
	cd $(PIPELINE) && $(UV_RUN) ruff check .
	cd $(PIPELINE) && $(UV_RUN) ruff check --config pyproject.toml ../scripts

typecheck:
	cd $(PIPELINE) && $(UV_RUN) mypy --strict src
	cd $(PIPELINE) && $(UV_RUN) mypy --strict ../scripts

# Branch coverage floor lives in pipeline/pyproject.toml.
test:
	cd $(PIPELINE) && $(UV_RUN) pytest --cov=src --cov-branch --cov-report=term

# Offline end to end: fixture page + trap CSV -> history -> snapshot -> site,
# no network, nothing written inside the checkout.
smoke:
	cd $(PIPELINE) && $(UV_RUN) caalgae \
		--fixture-page tests/fixtures/dataset-page-2026-10-12.html \
		--fixture-csv tests/fixtures/responses-traps_2026-10-09.csv \
		--run-today 2026-10-12 \
		--history $(TMP)/smoke/history.json \
		--snapshot-out $(TMP)/smoke/snapshot.json
	test -f $(TMP)/smoke/snapshot.json

# CQ-10: the wheel builds, and the schema ships inside it.
build:
	cd $(PIPELINE) && uv build --wheel --out-dir $(TMP)/dist
	cd $(PIPELINE) && $(UV_RUN) python -c "import sys, zipfile, glob; n = zipfile.ZipFile(glob.glob(sys.argv[1] + '/*.whl')[0]).namelist(); sys.exit(0 if 'caalgae/snapshot.v1.json' in n else 'wheel is missing caalgae/snapshot.v1.json')" $(TMP)/dist

audit:
	cd $(PIPELINE) && uv export --frozen --no-emit-project --format requirements-txt --quiet --output-file $(TMP)/audit/requirements.txt
	cd $(PIPELINE) && $(UV_RUN) pip-audit --strict --require-hashes --disable-pip -r $(TMP)/audit/requirements.txt
	osv-scanner scan --lockfile $(PIPELINE)/uv.lock

sast:
	uvx --python 3.12 --from semgrep==$(SEMGREP_VERSION) semgrep scan --config p/python --error --metrics=off --quiet $(PIPELINE)/src scripts

secrets:
	gitleaks dir . --no-banner --redact --exit-code 1
	gitleaks git . --no-banner --redact --exit-code 1

hygiene:
	cd $(PIPELINE) && $(UV_RUN) python ../scripts/check_hygiene.py --self-test
	cd $(PIPELINE) && $(UV_RUN) python ../scripts/check_hygiene.py

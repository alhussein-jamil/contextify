# contextify — common development and release build targets
#
# Usage:
#   make              # show targets
#   make build        # standalone binary (Linux)
#   make build-fast   # build without running tests first

.DEFAULT_GOAL := help

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VENV := $(ROOT)/.venv
export PATH := $(HOME)/.local/bin:$(PATH)

SKIP_TESTS ?= 0
INSTALL_DEV ?= 0

.PHONY: help venv install install-dev install-build test lint format pre-commit \
	build build-fast build-linux build-windows icons package smoke clean dist

help: ## Show available targets
	@printf "contextify build targets:\n\n"
	@grep -E '^[a-zA-Z0-9_.-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  %-18s %s\n", $$1, $$2}'

venv: ## Create local virtualenv (.venv)
	@test -d "$(VENV)" || uv venv "$(VENV)"

install: venv ## Editable install with dev + all extras
	@. "$(VENV)/bin/activate" && uv pip install -e ".[dev,all]"

install-dev: install ## Alias for install

install-build: venv ## Install PyInstaller build dependencies only
	@. "$(VENV)/bin/activate" && uv pip install -e ".[build]"

test: venv ## Run pytest
	@. "$(VENV)/bin/activate" && pytest tests/ -q --tb=short

lint: venv ## Run ruff check
	@. "$(VENV)/bin/activate" && ruff check src tests

format: venv ## Run ruff format
	@. "$(VENV)/bin/activate" && ruff format src tests

pre-commit: venv ## Run all pre-commit hooks
	@. "$(VENV)/bin/activate" && pre-commit run --all-files

icons: install-build ## Generate assets/contextify.ico from PNG (Windows builds)
	@. "$(VENV)/bin/activate" && python scripts/generate_icons.py

build-linux: ## Build standalone Linux executable (dist/contextify)
	SKIP_TESTS=$(SKIP_TESTS) INSTALL_DEV=$(INSTALL_DEV) bash scripts/build_linux.sh

build-windows: icons ## Build standalone Windows executable (dist/contextify.exe)
	SKIP_TESTS=$(SKIP_TESTS) INSTALL_DEV=$(INSTALL_DEV) powershell -File scripts/build_windows.ps1

build: build-linux ## Build standalone binary for this platform

build-fast: ## Build binary without running tests (SKIP_TESTS=1)
	$(MAKE) build SKIP_TESTS=1

package: ## Bundle dist/contextify into a versioned release zip
	bash scripts/package_release.sh

smoke: ## Smoke-test the standalone binary with a minimal PATH
	bash scripts/smoke_standalone.sh

dist: venv ## Build Python wheel and sdist into dist/
	@. "$(VENV)/bin/activate" && uv pip install build && uv build

clean: ## Remove build artifacts and caches
	rm -rf build dist *.egg-info .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

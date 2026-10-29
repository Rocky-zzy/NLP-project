PY ?= python

.PHONY: help install lint fmt test precommit clean

help:
	@echo "install     pip install -e .[dev]"
	@echo "lint        ruff check ."
	@echo "fmt         ruff format . && ruff check --fix ."
	@echo "test        pytest"
	@echo "precommit   pre-commit install"

install:
	$(PY) -m pip install -e ".[dev]"

lint:
	ruff check .

fmt:
	ruff format .
	ruff check --fix .

test:
	pytest

precommit:
	pre-commit install

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info

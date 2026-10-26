.PHONY: test test-system lint build check bench docs gifs clean

test:
	uv run pytest

test-system:
	uv run --isolated --python /usr/bin/python3 --with pytest --with pytest-mock pytest

lint:
	uv run ruff check
	uv run ruff format --check

build:
	uv run python scripts/build.py

check: build
	/usr/bin/env python3 scripts/smoke.py dist/Stashes.alfredworkflow $(or $(PYTHON),/usr/bin/python3)

bench:
	uv run python bench.py --python $(or $(PYTHON),/usr/bin/python3)

docs: gifs

gifs:
	uv run --with pillow python scripts/make_gifs.py

clean:
	rm -rf dist .pytest_cache .ruff_cache

.PHONY: test lint examples benchmark website screenshots brand
test:
	uv run pytest -q
lint:
	uv run ruff check && uv run ruff format --check && uv run mypy src/bergbot
examples:
	BERGBOT_OFFLINE=0 uv run python scripts/make_examples.py
benchmark:
	BERGBOT_OFFLINE=0 uv run bergbot benchmark --online
website:
	uv run python website/build.py
screenshots:
	uv run python scripts/screenshots.py
brand:
	uv run bergbot brand build

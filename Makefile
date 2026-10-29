.PHONY: test lint doctor re clean-local

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

lint:
	python3 -m compileall -q src tests tools
	@command -v ruff >/dev/null && ruff check . || echo "ruff not installed, skipped"

doctor:
	./bin/obsidian-translucent doctor

# Regenerates a local, beautified copy of your installed Obsidian for study. Output goes to
# .local/ (git-ignored). It is proprietary code: never commit or publish it.
re:
	./tools/re/make-study-copy.sh

clean-local:
	rm -rf .local/study

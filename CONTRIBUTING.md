# Contributing

Thanks for helping. This project is small on purpose: one binary patch, one blur helper, one CSS snippet.

## Ground rules

1. **No Obsidian code or binaries in the repo, ever** (see [docs/LEGAL.md](docs/LEGAL.md)). No extracted or beautified sources,
   no patched `.asar`, no long quotes in issues or PRs. Describe behaviour in your own words; quote only the short literal the
   patch targets.
2. Keep it dependency-free (Python standard library only at runtime).
3. Every behaviour change gets a test in `tests/` or an explanation of why it cannot be tested (the CSS and the compositor
   cannot be unit tested; say how you checked them, ideally with a before/after screenshot).

## Development

```bash
make test      # unit tests (python -m unittest)
make lint      # byte-compile, plus ruff if installed
make doctor    # check your machine
```

Run from a checkout with `./bin/obsidian-translucent ...`; no install needed. To test without touching your real settings, set `OBSIDIAN_TRANSLUCENT_DATA` and `OBSIDIAN_TRANSLUCENT_USER_DATA` to temporary directories (the tests do this).

## Updating the patch for a new Obsidian version

`doctor` or `run` fails with `PatchError` when the targeted code moved. To fix it:

1. `make re` builds a local, readable copy of *your* install in `.local/study/` (git-ignored; needs `pip install jsbeautifier`).
2. Find where the vault `BrowserWindow` options are built (see "Main process" in `docs/ARCHITECTURE.md` for what to look for).
3. Edit `VAULT_WINDOW` in `src/obsidian_translucent/patch.py`. `old` and `new` **must have equal length**. The tests enforce it.
4. Add the new Obsidian version to the "Tested versions" table in `docs/ARCHITECTURE.md` and a line to `CHANGELOG.md`.

## Supporting another desktop or compositor

Transparency is compositor-independent. Blur is the KDE part (`blur.py`). A new backend should be a separate module with the
same shape (`follow(pid, radius)`) and be selected in `cli.py`. Please include what you tested on.

## Pull requests

Small, focused, with a clear description of what you checked and on which Obsidian version, desktop and display scale.
Be kind in reviews; assume good faith.

# Legal notes

* Obsidian is proprietary software (its package metadata says `UNLICENSED`). This project is not affiliated with or endorsed
  by Obsidian / Dynalist Inc. Check Obsidian's own terms before using or modifying your copy.
* The build directory on your machine (`~/.local/share/obsidian-translucent/dist`) holds copies of Obsidian's launcher and a patched
  copy of its app, plus MIT-licensed `@electron/remote`. It is generated locally and is never part of this repository or its releases.
* The logo (`src/obsidian_translucent/assets/icon.svg`) is original artwork, deliberately unlike Obsidian's own logo.
* **This repository must never contain Obsidian's code or binaries:** no extracted or beautified sources, no patched
  `.asar` files, no vendored copies. The tool works on the user's own installed copy and writes its output outside the repo.
  `.gitignore` enforces this for the usual locations; reviewers should reject pull requests that add such files.
* `docs/ARCHITECTURE.md` records *facts about interfaces and behaviour* (IPC channel names, config keys, which option
  was changed and why) in our own words, so people can maintain the patch. It must not quote more of Obsidian's source than
  the single patched literal needed to apply the patch, and must not paste functions or files.
* The study helper (`make re`) generates a readable local copy for you to read. It is for personal interoperability study; keep
  it in `.local/` (git-ignored) and do not publish it.
* The code and CSS in this repository are MIT licensed (see `LICENSE`).

# depfix

A small CLI that automates the "read a Dependabot alert, check the package's release history, and update requirements.txt" workflow — built entirely on the Python standard library.

## What it does

Given a Dependabot security alert (in the same JSON shape GitHub's API returns) and a `requirements.txt`, `depfix`:

1. **Reads the alert** — package name, vulnerable version range, and the advisory's suggested `first_patched_version`.
2. **Checks whether the currently pinned version is actually affected** — if it's already outside the vulnerable range, nothing happens.
3. **Checks the package registry** (PyPI) before trusting the advisory's suggested version blindly: does that release actually exist, and has it been yanked? A yanked "fix" is not a fix.
4. **Falls back intelligently** if the suggested version is missing or yanked: picks the lowest available release that's both newer than the current pin and outside the vulnerable range, rather than jumping straight to the newest release (which could pull in unrelated breaking changes).
5. **Rewrites requirements.txt surgically** — only the version-pin lines that actually changed are touched. Comments, blank lines, extras (`package[extra]==1.0`), environment markers, and line order are all preserved exactly.

## Why this design

The "check package docs" step is implemented as a `PackageRegistry` abstraction (`registry.py`) with two implementations: a real one (`PyPIRegistry`) that queries `https://pypi.org/pypi/{name}/json` with `urllib`, and an in-memory fake (`InMemoryRegistry`) used throughout the test suite. This means the actual decision logic — which version to pick, when to fall back, when to do nothing — is fully unit-testable without any network access, while the real registry lookup is a thin, separately-reasoned-about layer on top.

## Usage

```bash
python -m depfix.cli --requirements requirements.txt --alerts alerts.json
```

Add `--dry-run` to see what would change without writing the file:

```bash
python -m depfix.cli --requirements requirements.txt --alerts alerts.json --dry-run
```

Example output:

```
[fixed] requests: 2.25.0 -> 2.31.0  (upgraded to the advisory's first_patched_version)
[skip]  alert #2 flask: pinned version is not affected by this alert

Updated requirements.txt
```

`alerts.json` is a JSON array in the shape returned by GitHub's `GET /repos/{owner}/{repo}/dependabot/alerts` endpoint — you can fetch it directly with `gh api repos/{owner}/{repo}/dependabot/alerts > alerts.json` if you have the GitHub CLI.

## Architecture

```
src/depfix/
  version.py        lightweight PEP440-ish version parsing/comparison + range matching
  requirements.py    requirements.txt parser/serializer (format-preserving)
  alerts.py          Dependabot alert JSON parsing
  registry.py         PackageRegistry abstraction: PyPIRegistry (real) + InMemoryRegistry (test fake)
  resolver.py          decides the target version for a single alert
  updater.py            orchestrates: parse -> resolve each alert -> rewrite
  cli.py                 argument parsing and the command-line entry point
```

## Testing

```bash
python -m unittest discover tests -v
```

41 tests, covering:

- **`test_version.py`** — version parsing, pre-release ordering, multi-clause range matching.
- **`test_requirements.py`** — parsing and rewriting requirements.txt, including the format-preservation guarantees (extras, markers, comments, trailing newline behavior).
- **`test_alerts.py`** — Dependabot alert JSON parsing.
- **`test_resolver.py`** — the version-resolution policy: preferring the advisory's patched version, falling back when it's yanked or missing, never regressing to an older version, doing nothing when the current pin isn't actually vulnerable.
- **`test_end_to_end.py`** — the full pipeline against real requirements.txt-shaped text and a multi-alert fixture (including a non-pip ecosystem alert and a dismissed alert, both correctly skipped), verified to only change the lines that needed it.
- **`test_cli.py`** — the actual `main()` entry point: argument parsing, exit codes, and error handling for missing files and malformed JSON, with the network-dependent registry mocked out.

Also manually smoke-tested against real files on disk end-to-end (see the example output above) — `requests` gets bumped from `2.25.0` to `2.31.0` while every other line in the file stays byte-for-byte identical.

## Limitations

- Only handles exact `==` pins in requirements.txt — a range like `requests>=2.0,<3.0` is left untouched rather than guessed at, since safely rewriting a range requires knowing more about the project's compatibility requirements than an alert alone provides.
- Only the `pip` ecosystem; alerts for other ecosystems (npm, etc.) are reported as skipped rather than silently ignored.
- The version comparison in `version.py` is a lightweight subset of PEP 440 (dotted release segments + `a`/`b`/`rc` pre-releases) — it doesn't handle epochs, post-releases, or local version identifiers. This covers the overwhelming majority of real-world PyPI packages and Dependabot version ranges; anything outside that scope raises a clear error rather than silently mis-comparing.
- Doesn't check whether bumping a package would break compatibility with other pinned packages (no dependency resolution) — it only confirms the target release itself exists and isn't yanked.

## License

MIT — see [LICENSE](LICENSE).

# Hamburg edition: source record

This edition contains 1,173 consolidated Hamburg acts from the official [Landesrecht Hamburg](https://www.landesrecht-hamburg.de/) source as observed on 12 November 2026. It covers 85.5% of 1,372 eligible current acts. The 199 absent image- or annex-bearing acts are recorded in [data/current-coverage.json](data/current-coverage.json). Earlier versions and intervening amendment history are outside scope.

**tools/source-corpus.json is the standalone build input.** It is one JSON object containing `country`, an `acts` array, a `laws` object, sources and version metadata. It includes all 1,173 resolved act records and 17,266 legal units, with the text tables intact. Its SHA-256 is **2db986201d64e65749e66125136ca4ce0e8dab1ad61537a85daa4a97db3863f3**, also recorded in [data/corpus.sha256](data/corpus.sha256). Original official-response hashes and source dates remain attached to each version.

**The root corpus.json is a repository descriptor.** Its integer `acts` value is a count, not an input array. It must not be supplied to the checker or builder as a source corpus. This distinction also applies to the published metadata-only baseline, whose descriptor records `acts: 0`. [tools/metadata-baseline-corpus.json](tools/metadata-baseline-corpus.json) supplies a valid empty input (`acts: []`) for that zero-act legal state; the published historical descriptor remains unchanged.

The following offline commands use the standalone input:

```powershell
New-Item -ItemType Directory -Path rebuild-input
Copy-Item tools/source-corpus.json rebuild-input/corpus.json
python -X utf8 tools/check_repo.py . --corpus rebuild-input/corpus.json
python -X utf8 tools/build.py rebuild-input --repo rebuilt --docs-date 2026-11-12
```

The build target must be a new directory. A clean build represents the current legal files and dates. Its commit hashes differ from this edition's appended history, which includes an earlier metadata scaffold and later labelled table-layout corrections; identical append-history hashes are not asserted.

Version dates are the source's Gesamtausgabe validity start or latest current provision-level Gültig ab date. Enactment dates are separate. No normative images, OCR text or gazette PDF are included.

Shared format and tools: **lexifina/world-law-ops main 590053183** (full identifier **590053183eb05e4288e221c23feb9e5d8d600e6c**). The edition also includes the three Hamburg-specific offline source modules and resolved source data. Source rights and attribution are in [NOTICE.md](NOTICE.md).

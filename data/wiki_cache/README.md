# Wikipedia extracts used for claim verification

One JSON file per FActScore prompt entity: `{"title": ..., "extract": ...}`.

- Source: English Wikipedia, retrieved via the MediaWiki API
  (`action=query&prop=extracts&explaintext=1`), 2026-11-08.
- Text is truncated to 12,000 characters.
- License: CC BY-SA 4.0. The text is included only to make the verification
  reproducible; it is not part of the project's own contribution.
- Two entries are disambiguation or stub pages (`Joeri Adams`, `Carlos Alfonso`)
  and carry no usable biography.

Consumed by `python -m confqa.extension.relabel --cache-dir data/wiki_cache --no-fetch`.

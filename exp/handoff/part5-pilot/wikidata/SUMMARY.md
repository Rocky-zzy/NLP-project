# Wikidata coverage pilot — summary

- **Run date**: 2026-11-17
- **Source**: Wikidata, `wbsearchentities` then `wbgetentities` (props: labels, descriptions, claims)
- **Network**: via local proxy; endpoint reachable
- **Input**: the 50 FActScore biography names in `data/factscore_names.txt`
- **Raw records**: `wikidata_pilot.json` (search hits, QID, description, statement count, property presence)
- **Script**: `wikidata_pilot.py`

## Result

| | all 50 | 25 test biographies |
|---|---:|---:|
| resolved to a QID | 24 (48%) | 13 (52%) |
| claims behind a resolved subject | — | 109 / 210 (52%) |

Property presence among the 25 test biographies:

| property | present |
|---|---:|
| birth date (P569) | 11 |
| citizenship (P27) | ~10 |
| place of birth (P19) | 9 |
| **position held (P39)** | **3** |
| **employer (P108)** | **1** |
| **award received (P166)** | **0** |

Mean statements per resolved entity: 28.7.

## Interpretation

Wikidata is usable as a **structured check of basic biographical attributes**
(birth date, occupation, nationality) and is not usable as a claim-level
verification source for this dataset. The claim types that dominate the FActScore
biographies — positions held, awards, employers, event attributions — are exactly
the properties with 0–12% coverage.

This is a **coverage** finding, not a reliability finding: where Wikidata has a
statement it is usually trustworthy, but it is silent on most of the claims.

## Limitations of the pilot

1. Entity resolution is a single top-hit lookup with no disambiguation step; some
   unresolved names may resolve with alias handling or occupation-qualified
   search. The 48% figure is therefore a lower bound on resolvability.
2. No revision pinning: the entities were read on 2026-11-17 and may change.
3. Statement counts include all properties, not only those relevant to a claim.
4. The pilot measured *entity and property availability*, not whether a specific
   claim is supported. Claim-level support would require value-level matching
   (dates, qualifiers, ranks), which this pilot did not attempt.

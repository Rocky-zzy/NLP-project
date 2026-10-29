# data

| Path | Content | Tracked |
|---|---|---|
| `raw/triviaqa/` | TriviaQA `rc.nocontext`, downloaded once | no |
| `raw/factscore/` | FActScore biography prompts | no |
| `splits/` | fixed calibration / dev / test ids | **yes** |
| `processed/` | intermediate, regenerable | no |

Splits are created once, committed, and never regenerated. Record the sha256 of
each split file in the report appendix so the numbers can be tied to an exact
partition.

Do not commit raw datasets: licenses differ and the files are large.

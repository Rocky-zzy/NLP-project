# Upstream repositories

Cloned into `third_party/` (git-ignored). Pinned commits below are what the
reported numbers must be tied to.

| Repository | Commit | Cloned | Size |
|---|---|---|---|
| [ConU](https://github.com/Zhiyuan-GG/Conformal-Uncertainty-Criterion) | `c0c450e8dbef489cfed28f585f1a4ddf0e66078b` (2025-07-11) | 2026-10-30 | 2.2 MB |
| [conformal-factual-lm](https://github.com/tatsu-lab/conformal-factual-lm) | `6022b4c90c6580f524f123b0cb97bbb61ab621d1` (2024-02-12) | 2026-10-30 | 14.7 MB |

---

## ConU

Six top-level scripts plus a slide deck. No `requirements.txt`, no data, no saved
generations — everything is regenerated from TriviaQA.

| Script | Role |
|---|---|
| `parse_triviaqa.py` | format TriviaQA rc.nocontext into prompts |
| `generate.py` | sample N answers per prompt and save them |
| `clean_open_domain_qa.py` | strip the sampled answers down to short strings |
| `open_domain_qa_similarity.py` | pairwise semantic similarity + similarity to gold |
| `conformal_uncertainty_criterion.py` | score, calibrate, build prediction sets, report coverage |

**Models referenced (all argparse defaults, all pointing at `D:\\projects\\cache_model\\...`):**

| Where | Default |
|---|---|
| `generate.py` | `llama-2-7b-chat-hf` |
| `conformal_uncertainty_criterion.py`, `clean_open_domain_qa.py` | `Qwen2.5-14B-Instruct` |
| `open_domain_qa_similarity.py` | `stsb-roberta-large` (CrossEncoder) + `Qwen2.5-3B-Instruct` |

Because these are argparse defaults, they can be overridden on the command line;
no source edit is needed to point at a new model directory.

Hard-coded values that do need attention:

- `os.environ["CUDA_VISIBLE_DEVICES"] = '0,1'` in `conformal_uncertainty_criterion.py:77`
- `seed_value = 10` (fine for reproducibility, but it is not exposed as a flag)
- `--correctness-threshold` defaults to 0.7 in the script while the README example
  passes 0.6 — **always pass it explicitly** and record the value with the result

### The filtering bias is confirmed

`conformal_uncertainty_criterion.py:88-94`, immediately before the split at line 97:

```python
# assumption: at least one acceptable generation
applied_generations = []
for generation in generations:
    ...
    if max(similarity_for_correctness_list) >= args.correctness_threshold:
        applied_generations.append(generation)

total_num = len(applied_generations)
num_cal = int(total_num * args.split_ratio)
```

Examples with no correct sample are dropped **before** calibration and test are
split, and `total_num` is then reported as if it were the dataset size. Our audit
has to restore the unfiltered denominator to report an honest coverage.

---

## conformal-factual-lm

Ships far more than we expected:

| Artifact | Content |
|---|---|
| `data/factscore_annotations.jsonl` | **50** biography prompts, every subclaim annotated `Y`/`N` |
| `out/factscore_subclaims_with_scores.jsonl` | the same claims with precomputed `gpt-score`, `frequency-score`, `random-score`, `baseline-score`, `noise` |
| `out/*_merged_*.jsonl` | filtered outputs produced by the paper's own runs |
| `out/*.png` | the paper's ranking / calibration / histogram figures |

**Consequence: Parts 1 and 3 of the factuality line need no LLM calls and no
GPU.** The calibration sweep in `src/calibrate_thresh.py` can be driven entirely
from the cached score files.

The scripts only need OpenAI when generating *new* outputs:

- `src/sayless.py:get_subclaims` — break a response into claims
- `src/sayless.py:get_frequency_scores` — sample 5 alternate outputs at T=1.0 and
  ask the LM to mark each claim as supported (1), contradicted (-1), or unrelated (0)
- `src/sayless.py:merge_subclaims` — rewrite the response from retained claims

Note that `get_frequency_scores` *is already* a cross-sample consistency score. The
Part 4 extension is therefore a fair substitution: same sampling budget, but
embedding-based semantic clustering replaces LLM-judged support.

`src/factscore.py` hard-codes `MODEL = "gpt-4"`, `ALPHA = 0.2`, and
`REQUIRED_FRAC_CORRECT = 0.96` (= 1 - α at α = 0.04, so a different α than the
0.2 used for the confidence method).

---

## How we will use them

- Keep `third_party/` **pristine**. Every override goes through CLI flags or our
  own code in `src/confqa/`, so the pinned commit plus a command line is enough
  to reproduce a number.
- The one behaviour we must change — disabling the ConU filter — will be a tracked
  patch under `patches/`, applied to a copy at run time, never a silent edit.
- Before generating anything new, check whether a cached artifact already answers
  the question. That is the default, not the exception.

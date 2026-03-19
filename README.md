# Creative Writing Benchmark v3

Evaluates creative writing quality of LLMs using rubric scoring + Elo pairwise matchups, from the [EQ-Bench Creative Writing leaderboard](https://eqbench.com/creative_writing.html).

**This fork adds a modular Narrative Pipeline** — a multi-step generation process (warmup → structural beats → story) fully controllable via CLI flags.

## Quick Start

### 1. Setup

```bash
git clone https://github.com/maxzhuyt/creative-writing-bench.git
cd creative-writing-bench

pip install requests python-dotenv numpy scipy tqdm glicko2 nltk joblib trueskill

python -c "import nltk; nltk.download('punkt'); nltk.download('cmudict')"
```

### 2. Configure API Keys

```bash
cp .env.example .env
# Edit .env — add your OpenRouter (or Anthropic) API keys for TEST and JUDGE models
```

### 3. Unzip Leaderboard Data

Required for Elo comparison against existing models:

```bash
unzip creative_bench_runs.zip
unzip elo_results.zip
```

### 4. Run

```bash
# Vanilla (no pipeline, leaderboard-comparable)
python creative_writing_bench.py \
    --test-model "anthropic/claude-opus-4-6" \
    --judge-model "anthropic/claude-sonnet-4" \
    --run-id vanilla --iterations 3 --threads 4

# With narrative pipeline (title warmup → beats → story)
python creative_writing_bench.py \
    --test-model "anthropic/claude-opus-4-6" \
    --judge-model "anthropic/claude-sonnet-4" \
    --step0 title --run-id full --iterations 3 --threads 4
```

Add `--no-elo` for rubric score only (faster, cheaper).

---

## Narrative Pipeline

An optional multi-step generation process that replaces single-shot prompting:

```
Step 0: Warmup              Step 1: Beats               Step 2: Story
Generate a structural       Adapt the beat sheet         Write the story following
beat sheet from a            to the writing prompt        the structural beats
reference story
```

Enable by adding `--step0` to your command. If omitted, the benchmark runs in vanilla mode (single-shot generation, identical to the original benchmark).

### Pipeline Configurations

Every configuration is a CLI flag — no code edits needed:

```bash
# ── Warmup modes (--step0) ────────────────────────────────────────

# Title: LLM generates beats from a famous story title (20 in pool)
--step0 title

# Full text: LLM reads an entire short story and extracts beats (20 NYer stories)
--step0 fulltext --step0-sources-dir /path/to/stories/

# Pre-computed: no API call for step 0, uses saved templates (cheapest)
--step0 precomputed

# No warmup: step 1 generates beats from scratch
--step0 none

# ── Warmup style (--step0-style) ──────────────────────────────────

--step0-style c1_specific   # 7 scene-level beats with techniques (default)
--step0-style baseline       # 5-point beat sheet
--step0-style c2_abstract    # 3 universal archetypal moves

# ── Fix warmup source (--step0-source) ────────────────────────────

--step0-source A1            # Always use Le Guin (title mode)
--step0-source 00015         # Always use this NYer story (fulltext mode)
# Omit for random sampling each iteration

# ── Beat generation (--step1) ─────────────────────────────────────

--step1 default              # Standard beat adaptation (default)
--step1-max-beats 3          # Short beat list (3 beats only)
--step1 my_prompts.json      # Custom prompt template from JSON file
--step1 none                 # Skip beats → step 0 auto-skipped → vanilla
```

### Full Example Commands

```bash
BASE="python creative_writing_bench.py \
    --test-model anthropic/claude-opus-4-6 \
    --judge-model anthropic/claude-sonnet-4 \
    --iterations 3 --threads 4"

# Full pipeline (title warmup, default beats)
$BASE --step0 title --run-id full

# Pre-computed warmup (cheapest)
$BASE --step0 precomputed --run-id precomp

# Full-text warmup from NYer corpus
$BASE --step0 fulltext --step0-sources-dir ./my_stories --run-id fulltext

# Ablate warmup (beats from scratch, no reference)
$BASE --step0 none --run-id no_warmup

# Short beats (3 only)
$BASE --step0 title --step1-max-beats 3 --run-id short_beats

# Fixed warmup (always Le Guin)
$BASE --step0 title --step0-source A1 --run-id fixed_leguin

# Abstract warmup style
$BASE --step0 title --step0-style c2_abstract --run-id abstract

# Custom step1 prompts from JSON
$BASE --step0 title --step1 prompts.json --run-id custom

# Vanilla (no pipeline)
$BASE --run-id vanilla

# Rubric only (skip Elo)
$BASE --step0 title --run-id full_rubric --no-elo
```

### Pipeline Flag Reference

| Flag | Options | Default |
|---|---|---|
| `--step0` | `title`, `fulltext`, `precomputed`, `none` | *(not set = vanilla)* |
| `--step0-style` | `baseline`, `c1_specific`, `c2_abstract` | `c1_specific` |
| `--step0-source` | Source ID (e.g., `A1`, `00015`) | random |
| `--step0-templates` | Path to JSON | `data/narrative_step0_templates.json` |
| `--step0-sources-dir` | Path to .txt directory | *(required for fulltext)* |
| `--step1` | `default`, `none`, or path to JSON | `default` |
| `--step1-max-beats` | Integer | *(no limit)* |

**Key rule:** `--step1 none` forces vanilla mode. Step 0 is automatically skipped because a warmup without beats is meaningless.

### Custom Step 1 Prompts

Create a JSON file with a list of prompt template strings. Use `{warmup}` and `{writing_prompt}` as placeholders:

```json
[
  "Reference beats:\n---\n{warmup}\n---\n\nCreate a minimalist 3-act outline for:\n{writing_prompt}"
]
```

Then: `--step1 my_prompts.json`

### Pipeline Implementation

Defined in `core/narrative_pipeline.py`. Each step is a `PipelineStep` object with access to all prior step outputs via `PipelineContext`. See the module docstring for programmatic usage.

---

## How the Benchmark Works

1. **Generation:** 32 writing prompts × 3 iterations = 96 items, at temperature 0.7, min_p 0.1.
2. **Rubric Scoring:** Each piece judged by Claude Sonnet 4 against a detailed rubric (22 criteria).
3. **Initial Elo Inference:** Rubric score used to estimate starting Elo position.
4. **Pairwise Matchups:** Head-to-head comparisons against neighboring models, scored by criteria with win margins.
5. **Glicko-2 Rating:** Iterative Elo calculation until positions stabilize.
6. **Comprehensive Matchups:** Final dense comparisons with stable neighbors.
7. **Normalization:** Raw Elo anchored to reference models for cross-time comparability.

More info: [eqbench.com/about.html#creative-writing-v3](https://eqbench.com/about.html#creative-writing-v3)

## CLI Reference

| Flag | Description | Default |
|---|---|---|
| `--test-model` | Model to evaluate (required) | — |
| `--judge-model` | Judge model (required; use `anthropic/claude-sonnet-4` for leaderboard parity) | — |
| `--runs-file` | JSON file for run data. **Must use `creative_bench_runs.json` for Elo comparison.** | `creative_bench_runs.json` |
| `--run-id` | Unique prefix for this run | auto-generated |
| `--iterations` | Iterations per prompt (recommended: 3) | 1 |
| `--threads` | Parallel API calls | 4 |
| `--no-elo` | Skip Elo matchups (rubric only) | false |
| `--redo-judging` | Re-judge existing generations | false |
| `--verbosity` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| `--narrative-pipeline` | *(Legacy)* Path to step0 templates JSON | — |

See [Pipeline Flag Reference](#pipeline-flag-reference) for `--step0`/`--step1` flags.

## Output

- **Rubric score** (0-100): Aggregate across 22 criteria, judged per-piece in isolation.
- **Elo score** (normalized): Relative rating from pairwise matchups. Primary leaderboard metric.
- Run data saved to `--runs-file` (generations, scores, intermediates).
- Elo results saved to `elo_results.json`.

## Estimated Costs (Sonnet 4 judge via OpenRouter)

| Run Type | Approx. Cost |
|---|---|
| Vanilla (rubric only) | ~$5 |
| Vanilla (rubric + Elo) | ~$10-15 |
| Narrative pipeline (rubric only) | ~$8 |
| Narrative pipeline (rubric + Elo) | ~$15-20 |

## Citation

```bibtex
@misc{creative-writing-bench-v3,
  author = {Samuel J Paech},
  title = {EQ-Bench Creative Writing Benchmark v3},
  year = {2025},
  publisher = {GitHub},
  journal = {GitHub repository},
  howpublished = {\url{https://github.com/EQ-bench/creative-writing-bench}}
}
```

# Creative Writing Benchmark v3

Welcome to the Creative Writing Benchmark v3 repository! This benchmark evaluates the creative writing capabilities of large language models using a hybrid rubric and Elo scoring system, designed for enhanced discrimination, especially at the top end of model performance. This is the system used for the Creative Writing leaderboard on [EQ-Bench.com](https://eqbench.com/creative_writing.html).

**This fork adds a modular Narrative Pipeline** that replaces single-shot generation with a multi-step process (warmup → structural beats → story), enabling systematic ablation studies.

## Narrative Pipeline: Architecture and Ablation Guide

The pipeline is defined in `core/narrative_pipeline.py`. Each step is an independent object that can be added, removed, replaced, or configured.

### Pipeline Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Step 0: Warmup  │ ──► │  Step 1: Beats    │ ──► │  Step 2: Story   │
│  (beat sheet     │     │  (adapted to-do   │     │  (final output   │
│   from reference)│     │   list for prompt) │     │   for judging)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

All steps share a `PipelineContext` that accumulates outputs. Each step can read any previous step's output by name.

### Available Steps

| Step Class | Name | API Call? | Description |
|---|---|---|---|
| `WarmupStep` | warmup | No | Select from pre-computed beat sheet templates |
| `GenerateWarmupStep` | warmup | Yes | Generate a beat sheet live via API call |
| `BeatSheetStep` | beats | Yes | Adapt warmup beats to the writing prompt |
| `StoryWriteStep` | story | Yes | Write the story from structural beats |
| `VanillaStep` | story | Yes | Single-shot generation (original benchmark behavior) |

### Pre-computed Warmup Templates

The file `data/narrative_step0_templates.json` contains 6 pre-generated structural beat sheets, each extracted from a different reference story using the `c1_specific` prompt style (7 scene-level beats with named techniques). These were generated once via `llm-fiction-writing/step0_experiments.py` and are reused across all benchmark runs for reproducibility and cost savings (no API call needed at step 0).

| source_id | Type | Reference Story |
|---|---|---|
| A1 | Famous | The Ones Who Walk Away from Omelas (Le Guin) |
| A2 | Famous | The Lottery (Jackson) |
| A4 | Famous | The Yellow Wallpaper (Gilman) |
| B1 | Contemporary | The Fellow (New Yorker) |
| B2 | Contemporary | Poor Girl (New Yorker) |
| B3 | Contemporary | The Dog (New Yorker) |

One template is randomly sampled per generation task. To fix a specific template for ablation, use `source_id` when constructing the pipeline (see ablation examples below).

### Preset Pipelines

```python
from core.narrative_pipeline import *

templates = {"A1": "...", "B1": "..."}  # pre-computed step0 data

# Full 3-step pipeline with pre-computed warmups
make_full_pipeline(templates)

# Full 3-step with live warmup generation (no templates needed)
make_live_warmup_pipeline(style="c1_specific")

# Ablate warmup: beats generated from scratch
make_no_warmup_pipeline()

# Ablate beats: warmup only, then vanilla story
make_no_beats_pipeline(templates)

# Vanilla: equivalent to standard benchmark
make_vanilla_pipeline()
```

### Ablation Examples

To run ablation experiments, construct pipelines programmatically. Here are common configurations:

```python
from core.narrative_pipeline import *
import json

# Load pre-computed templates
with open("data/narrative_step0_templates.json") as f:
    raw = json.load(f)
    templates = {e["source_id"]: e["step0"] for e in raw}

# ── Ablation 1: Remove warmup (step 0) ──────────────────────────
# Beats are generated from scratch without a reference beat sheet
pipeline = NarrativePipeline([
    BeatSheetStep(),          # no warmup context available
    StoryWriteStep(),
])

# ── Ablation 2: Remove beats (step 1) ───────────────────────────
# Warmup is loaded but goes unused; story is vanilla
pipeline = NarrativePipeline([
    WarmupStep(templates=templates),
    StoryWriteStep(),         # no beats context → falls back to vanilla prompt
])

# ── Ablation 3: Short beat list ──────────────────────────────────
pipeline = NarrativePipeline([
    WarmupStep(templates=templates),
    BeatSheetStep(max_beats=3),   # "Limit to exactly 3 beats."
    StoryWriteStep(),
])

# ── Ablation 4: Fix warmup to a single reference story ──────────
pipeline = NarrativePipeline([
    WarmupStep(templates=templates, source_id="A1"),  # always Le Guin
    BeatSheetStep(),
    StoryWriteStep(),
])

# ── Ablation 5: Live warmup with different styles ────────────────
# c1_specific (default): 7 scene beats + techniques + memorability
# baseline: 5-point beat sheet
# c2_abstract: 3 universal archetypal moves
pipeline = NarrativePipeline([
    GenerateWarmupStep(style="baseline"),
    BeatSheetStep(),
    StoryWriteStep(),
])

# ── Ablation 6: Live warmup with a specific reference ────────────
pipeline = NarrativePipeline([
    GenerateWarmupStep(style="c1_specific", reference_id="A8"),  # Rashōmon
    BeatSheetStep(),
    StoryWriteStep(),
])

# ── Ablation 7: Custom prompts ──────────────────────────────────
pipeline = NarrativePipeline([
    GenerateWarmupStep(
        custom_prompt='Analyze the narrative structure of "{ref}". '
                      'Focus on how tension is built and released.'
    ),
    BeatSheetStep(
        custom_instruction=(
            "Reference beats:\n---\n{warmup}\n---\n\n"
            "Create a to-do list for this story:\n{writing_prompt}\n"
            "Limit to {max_beats} beats."
        ),
        max_beats=5,
    ),
    StoryWriteStep(),
])

# ── Vanilla baseline (no pipeline) ──────────────────────────────
pipeline = NarrativePipeline([
    VanillaStep(),
])
```

### Running Ablations via the Benchmark

To run an ablation through the full benchmark pipeline (with judging and Elo), modify `core/benchmark.py` where the pipeline is constructed, or write a short script:

```python
from core.benchmark import run_eq_bench_creative
from core.narrative_pipeline import *

# This script bypasses --narrative-pipeline CLI arg and injects
# the pipeline directly. See benchmark.py for the full argument list.

# Example: run with no-warmup ablation
# You would need to modify benchmark.py to accept a pipeline object
# directly, or construct it in the narrative_pipeline loading section.
```

Alternatively, for quick ablation testing, use the CLI with different `--narrative-pipeline` files (each containing different pre-computed templates) and different `--run-id` values to keep results separate.

### GenerateWarmupStep: Reference Stories

When using `GenerateWarmupStep` (live warmup generation), one of 20 famous short stories is randomly selected as the reference. The default pool spans diverse narrative traditions:

| ID | Story | Technique Focus |
|---|---|---|
| A1 | The Ones Who Walk Away from Omelas (Le Guin) | Moral philosophy |
| A2 | The Lottery (Jackson) | Suspense/Reveal |
| A3 | Hills Like White Elephants (Hemingway) | Subtext/Dialogue |
| A4 | The Yellow Wallpaper (Gilman) | Unreliable narrator |
| A5 | A Good Man Is Hard to Find (O'Connor) | Violence/Grace |
| A6 | The Garden of Forking Paths (Borges) | Metafiction/Structure |
| A7 | The Metamorphosis (Kafka) | Surrealism/Premise |
| A8 | Rashomon (Akutagawa) | Subjectivity/Perspective |
| A9 | The Necklace (Maupassant) | Irony/Pacing |
| A10 | The Overcoat (Gogol) | Pathos/Character |
| A11 | Girl (Kincaid) | Form/Prose Rhythm |
| A12 | Axolotl (Cortazar) | Magical Realism/Identity |
| A13 | Cathedral (Carver) | Minimalism/Dirty Realism |
| A14 | The Lady with the Dog (Chekhov) | Modern Realism |
| A15 | Araby (Joyce) | Epiphany/Coming-of-age |
| A16 | A Very Old Man with Enormous Wings (Marquez) | Imagery |
| A17 | Sonny's Blues (Baldwin) | Voice/Narrative Soul |
| A18 | The Fifth Story (Lispector) | Narrative Experimentation |
| A19 | A Madman's Diary (Lu Xun) | Allegory/Social Critique |
| A20 | The Bear Came Over the Mountain (Munro) | Handling of Time/Memory |

### Warmup Styles

Three prompt styles are available for `GenerateWarmupStep`:

| Style | Description |
|---|---|
| `c1_specific` (default) | 7 scene-level beats with named techniques and memorability analysis |
| `baseline` | 5-point structural beat sheet |
| `c2_abstract` | 3 universal archetypal moves (no plot specifics) |

---

## Quick Start

### Prerequisites

*   Python 3.x
*   API keys for the test and judge models (compatible with OpenAI/OpenRouter API format).

### Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/maxzhuyt/creative-writing-bench.git
    cd creative-writing-bench
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    # Or manually:
    # pip install requests python-dotenv numpy scipy tqdm glicko2 nltk joblib trueskill
    ```
    You also need to download NLTK data:
    ```python
    import nltk
    nltk.download('punkt')
    nltk.download('cmudict')
    ```

3.  **Configure API Keys:**
    *   Copy the example environment file: `cp .env.example .env`
    *   Edit the `.env` file and add your API keys and desired endpoint URLs for the test and judge models.

4.  **Unzip leaderboard data (for Elo comparison):**
    ```bash
    unzip creative_bench_runs.zip
    unzip elo_results.zip
    ```

### Running with the Narrative Pipeline

```bash
python creative_writing_bench.py \
    --test-model "anthropic/claude-sonnet-4-6" \
    --judge-model "anthropic/claude-sonnet-4" \
    --runs-file "creative_bench_runs.json" \
    --narrative-pipeline "data/narrative_step0_templates.json" \
    --run-id "narrative_run" \
    --iterations 3 \
    --threads 4
```

Add `--no-elo` to skip pairwise matchups (faster, cheaper, rubric score only).

### Running the Benchmark (Standard / Vanilla)

For a leaderboard-comparable score using vanilla single-shot generation:

```bash
python creative_writing_bench.py \
    --test-model "your-model-provider/your-model-name" \
    --judge-model "anthropic/claude-sonnet-4" \
    --runs-file "creative_bench_runs.json" \
    --run-id "my_run" \
    --iterations 3 \
    --threads 4
```

---

## How the Benchmark Works

The evaluation process involves several steps:

1.  **Generation:** The model under test generates responses to 32 distinct writing prompts across 3 iterations (96 items total). Generation uses a temperature of 0.7 and min_p of 0.1 to encourage creativity while maintaining some consistency.
2.  **Rubric Scoring:** Each generated piece is individually assessed by a judge model (Anthropic's Claude Sonnet 4 recommended for leaderboard parity) against a comprehensive rubric.
3.  **Initial Elo Inference:** The aggregate rubric score is used to estimate an initial Elo rating for the model being evaluated relative to existing models.
4.  **Pairwise Matchups (Sparse):** The model is compared against neighboring models on the leaderboard using pairwise matchups. The judge determines the better output across several criteria, assigning a score margin (using `+` symbols).
5.  **Glicko Calculation:** Elo scores are calculated using the Glicko-2 rating system, modified to incorporate the win margin (number of `+`'s) from pairwise comparisons. This process loops until model positions stabilize.
6.  **Pairwise Matchups (Comprehensive):** More thorough pairwise comparisons are conducted with the model's final neighbors.
7.  **Final Elo Calculation:** The definitive leaderboard Elo score is computed based on all comparisons.
8.  **Normalization:** Raw Elo scores are normalized by anchoring specific models (e.g., `deepseek/deepseek-r1` to 1500, `mistralai/ministral-3b` to 200) to ensure comparability over time.

More info here: [https://eqbench.com/about.html#creative-writing-v3](https://eqbench.com/about.html#creative-writing-v3)

## CLI Arguments

*   `--test-model`: Identifier for the model you want to evaluate.
*   `--judge-model`: Identifier for the judge model (use `anthropic/claude-sonnet-4` for leaderboard scores).
*   `--runs-file`: Path to the JSON file storing run data. **To get an Elo score comparable to the EQ-Bench leaderboard, you *must* use the `creative_bench_runs.json` file provided in this repository**, as it contains the necessary historical data for Elo calculation.
*   `--iterations`: Number of generation iterations per prompt (default and recommended: 3).
*   `--run-id`: A unique prefix for this specific run attempt.
*   `--threads`: Number of parallel threads for generation and judging (adjust based on your API rate limits).
*   `--narrative-pipeline`: Path to a JSON file with pre-computed step0 templates. Enables the 3-step narrative pipeline.
*   `--no-elo`: Skip the Elo pairwise matchup stage (rubric score only).
*   `--redo-judging`: Re-run the judge step on existing generated items.
*   `--verbosity`: Logging level (e.g., `DEBUG`, `INFO`).

## Canonical Leaderboard Results

Leaderboard results are saved in `creative_bench_runs.zip` and `elo_results.zip`. If you would to compare a result against the leaderboard models, unzip these into the root repository dir and the eval pipeline will use them in ELO matchups (assuming you are using default run file paths), giving you a leaderboard-comparable result.

These canonical zip files may not be always updated, so if you need the latest results, ping contact@eqbench.com.

## Understanding the Output

*   Progress will be logged to the console.
*   Detailed run data, including generated text and judge scores, is saved in the specified `--runs-file` (e.g., `creative_bench_runs.json`).
*   Elo analysis results, including pairwise comparisons and final ratings, are stored in `elo_results.json`.
*   The final normalized Elo score (`elo_norm`) for your test model will be printed at the end and saved in `elo_results.json`. This is the score comparable to the EQ-Bench leaderboard.

## Estimated Costs (using Sonnet 4 as judge via OpenRouter)

| Run Type | Approx. Cost |
|---|---|
| Vanilla (rubric only) | ~$5 |
| Vanilla (rubric + Elo) | ~$10-15 |
| Narrative pipeline (rubric only) | ~$8 |
| Narrative pipeline (rubric + Elo) | ~$15-20 |

## Scoring System: Rubric vs. Elo

*   **Rubric Score:** An aggregate score based on judging each piece in isolation against a detailed rubric. Provides insight into specific criteria but can saturate at high performance levels.
*   **Elo Score:** A relative rating derived from pairwise comparisons against other models. More discriminative, especially at the top end, but sensitive to the pool of compared models.

These scores measure different aspects and may not always align perfectly due to judging methodology differences and criteria variations. The **normalized Elo score (`elo_norm`)** is the primary metric used for the leaderboard ranking.

## Bias Mitigation

We attempt to control for several biases common in pairwise LLM judging:

*   **Length Bias:** Mitigated by truncating outputs to 4000 characters.
*   **Position Bias:** Mitigated by running comparisons in both A/B and B/A orders and averaging.
*   **Verbosity/Poetic Incoherence Bias:** Addressed through specific judging criteria penalizing excessive or incoherent stylistic choices.

Biases **not** explicitly controlled for include potential judge self-bias, positivity/negativity bias, NSFW content aversion (smut bias), stylistic preferences, and "slop" bias (favoring overused tropes). Be mindful of these when interpreting results.

## Limitations

*   **Subjectivity:** Creative quality is subjective; the judge's assessment may differ from human preferences.
*   **Judge Limitations:** Sonnet 4 is good but not infallible; it may miss nuances humans perceive.
*   **Not a Roleplay Eval:** The benchmark doesn't assess conversational RP skills.
*   **English Only:** Currently evaluates English language writing only.
*   **Cost:** Running the benchmark involves API costs (approx. $10 per model using Sonnet 4 as judge).

**Always view benchmark scores as a guide, not absolute truth. Read the sample outputs!**

## Citation

If you use this benchmark in your work, please cite the repository:

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

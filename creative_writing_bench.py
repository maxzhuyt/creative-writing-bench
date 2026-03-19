# creative_writing_bench.py

"""
Main entry for the Creative Writing Benchmark with iteration-based generation.
"""
import argparse
import sys
import signal
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from utils.logging_setup import setup_logging, get_verbosity
from utils.file_io import load_json_file # Added for summary box
from core.benchmark import run_eq_bench_creative

load_dotenv()

def signal_handler(signum, frame):
    print(f"\n[DEBUG] Signal {signum} caught! Stopping gracefully.")
    sys.exit(1)

def print_summary_box(run_key: str, runs_file: str, run_elo: bool):
    """Prints a formatted summary box of the benchmark run."""
    try:
        runs = load_json_file(runs_file)
        run_data = runs.get(run_key)
        if not run_data:
            print(f"\nError: Could not find run data for key {run_key} in {runs_file}")
            return

        test_model = run_data.get("test_model", "N/A")
        judge_model = run_data.get("judge_model", "N/A")
        start_time_str = run_data.get("start_time")
        end_time_str = run_data.get("end_time")

        duration_str = "N/A"
        if start_time_str and end_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str)
                end_time = datetime.fromisoformat(end_time_str)
                # Ensure timezone awareness for subtraction if needed, assuming UTC if not specified
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)

                duration = end_time - start_time
                total_seconds = duration.total_seconds()
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_str = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
            except ValueError:
                duration_str = "Error parsing time"


        results = run_data.get("results", {}).get("benchmark_results", {})
        rubric_score = results.get("creative_score_0_20", "N/A")
        eq_score = results.get("eqbench_creative_score", "N/A")
        elo_raw = results.get("elo_raw", "N/A")
        elo_norm = results.get("elo_normalized", "N/A")

        if isinstance(rubric_score, (int, float)):
            rubric_score_str = f"{rubric_score:.2f}"
        else:
            rubric_score_str = str(rubric_score)

        if isinstance(eq_score, (int, float)):
            eq_score_str = f"{eq_score:.2f}"
        else:
            eq_score_str = str(eq_score)

        if not run_elo:
            elo_raw_str = "Skipped"
            elo_norm_str = "Skipped"
        else:
            elo_raw_str = str(elo_raw) if elo_raw != "N/A" else "N/A"
            elo_norm_str = str(elo_norm) if elo_norm != "N/A" else "N/A"


        box_width = 60
        print("\n" + "╔" + "═" * (box_width - 3) + "╗")
        print(f"║ {'EQ-Bench Creative Writing':^{box_width - 5}} ║")
        print("╠" + "═" * (box_width - 3) + "╣")
        print(f"║ {'Run Key:':<15} {run_key:<{box_width - 21}} ║")
        print(f"║ {'Test Model:':<15} {test_model:<{box_width - 21}} ║")
        print(f"║ {'Judge Model:':<15} {judge_model:<{box_width - 21}} ║")
        print(f"║ {'Duration:':<15} {duration_str:<{box_width - 21}} ║")
        print("╠" + "═" * (box_width - 3) + "╣")
        print(f"║ {'Rubric Score (0-100):':<25} {eq_score_str:<{box_width - 31}} ║")        
        print("╠" + "═" * (box_width - 3) + "╣")
        print(f"║ {'Elo Raw:':<30} {elo_raw_str:<{box_width - 36}} ║")
        print(f"║ {'Leaderboard Elo (Normalised):':<30} {elo_norm_str:<{box_width - 36}} ║")
        print("╚" + "═" * (box_width - 3) + "╝")

    except Exception as e:
        print(f"\nError generating summary box: {e}")
        logging.error(f"Error generating summary box for run {run_key}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="Run Creative Writing Benchmark (with iterations).")
    parser.add_argument("--test-model", required=True, help="The model name or identifier for the test model.")
    parser.add_argument("--judge-model", required=True, help="The model name or identifier for the judge model.")
    parser.add_argument("--runs-file", default="creative_bench_runs.json", help="File where run data is stored.")
    parser.add_argument("--run-id", help="Optional: Resume or create a run with this ID prefix")
    parser.add_argument("--threads", type=int, default=4, help="Number of parallel threads.")
    parser.add_argument("--verbosity", choices=['DEBUG','INFO','WARNING','ERROR','CRITICAL'], default="INFO")
    parser.add_argument("--redo-judging", action="store_true", default=False, help="Re-run the judge step on existing items.")
    parser.add_argument("--creative-prompts-file", default="data/creative_writing_prompts_v3.json")
    parser.add_argument("--criteria-file", default="data/creative_writing_criteria.txt")
    parser.add_argument("--negative-criteria-file", default="data/negative_criteria.txt")
    parser.add_argument("--judge-prompt-file", default="data/creative_writing_judging_prompt.txt")
    parser.add_argument("--save-interval", type=int, default=2, help="How often to save partial progress.")
    parser.add_argument("--iterations", type=int, default=1, help="How many iteration passes to run (one seed per iteration).")
    # --- ELO ---
    parser.add_argument("--no-elo", action="store_true", default=False, help="Disable the ELO analysis step.")

    # --- Narrative pipeline ---
    parser.add_argument("--narrative-pipeline", default=None,
                        help="(Legacy) Path to step0 templates JSON. Equivalent to --step0 precomputed --step0-templates <path>.")

    pipe = parser.add_argument_group("Pipeline configuration")
    pipe.add_argument("--step0", type=str, default=None,
                      choices=["title", "fulltext", "precomputed", "none"],
                      help=("Step 0 warmup mode. "
                            "'title': generate beats from famous story title. "
                            "'fulltext': generate beats from full story text. "
                            "'precomputed': use pre-generated templates. "
                            "'none': skip warmup. "
                            "If omitted and --narrative-pipeline is set, defaults to 'precomputed'. "
                            "If both omitted, no pipeline (vanilla)."))
    pipe.add_argument("--step0-style", type=str, default="c1_specific",
                      choices=["baseline", "c1_specific", "c2_abstract"],
                      help="Step 0 prompt style (default: c1_specific)")
    pipe.add_argument("--step0-source", type=str, default=None,
                      help="Fix a specific source ID for step0 (e.g., 'A1'). Omit to randomly sample.")
    pipe.add_argument("--step0-templates", type=str, default="data/narrative_step0_templates.json",
                      help="JSON file for precomputed mode")
    pipe.add_argument("--step0-sources-dir", type=str, default=None,
                      help="Directory of .txt files for fulltext mode")
    pipe.add_argument("--step1", type=str, default="default",
                      help=("Step 1 beat generation. "
                            "'default': standard beat adaptation. "
                            "'none': skip beats (vanilla). "
                            "Or path to JSON with custom prompts."))
    pipe.add_argument("--step1-max-beats", type=int, default=None,
                      help="Limit step1 to N beats")

    args = parser.parse_args()

    # Resolve legacy --narrative-pipeline flag
    if args.narrative_pipeline and args.step0 is None:
        args.step0 = "precomputed"
        args.step0_templates = args.narrative_pipeline
    setup_logging(get_verbosity(args.verbosity))

    # Hook signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    run_elo_flag = not args.no_elo # Determine if ELO should run

    # --- Build narrative pipeline from CLI flags ---
    pipeline = None
    if args.step0 is not None:
        from core.narrative_pipeline import (
            NarrativePipeline, WarmupStep, GenerateWarmupStep,
            GenerateWarmupFromTextStep, BeatSheetStep, StoryWriteStep, VanillaStep,
        )
        from utils.file_io import load_json_file as _load

        if args.step1 == "none":
            pipeline = NarrativePipeline([VanillaStep()])
        else:
            steps = []
            # Step 0
            if args.step0 == "title":
                steps.append(GenerateWarmupStep(
                    style=args.step0_style, reference_id=args.step0_source))
            elif args.step0 == "fulltext":
                steps.append(GenerateWarmupFromTextStep(
                    style=args.step0_style, sources_dir=args.step0_sources_dir,
                    fixed_source_id=args.step0_source))
            elif args.step0 == "precomputed":
                raw = _load(args.step0_templates)
                templates = {}
                for e in raw:
                    sid = e["source_id"]
                    if sid not in templates and e.get("step0"):
                        templates[sid] = e["step0"]
                steps.append(WarmupStep(templates=templates, source_id=args.step0_source))
            # step0 == "none": no warmup step

            # Step 1
            if args.step1 == "default":
                steps.append(BeatSheetStep(max_beats=args.step1_max_beats))
            elif args.step1 != "none":
                import json
                with open(args.step1) as f:
                    custom = json.load(f)
                steps.append(BeatSheetStep(
                    custom_instruction=custom[0], max_beats=args.step1_max_beats))

            # Step 2
            steps.append(StoryWriteStep())
            pipeline = NarrativePipeline(steps)

        logging.info(f"Narrative pipeline: {pipeline}")

    run_key = run_eq_bench_creative(
        test_model=args.test_model,
        judge_model=args.judge_model,
        runs_file=args.runs_file,
        num_threads=args.threads,
        run_id=args.run_id,
        creative_prompts_file=args.creative_prompts_file,
        creative_criteria_file=args.criteria_file,
        negative_criteria_file=args.negative_criteria_file,
        judge_prompt_file=args.judge_prompt_file,
        redo_judging=args.redo_judging,
        save_interval=args.save_interval,
        iterations=args.iterations,
        run_elo=run_elo_flag,
        narrative_pipeline_obj=pipeline,
    )

    logging.info(f"Creative writing benchmark completed. Run key: {run_key}")
    print(f"\nCreative writing benchmark completed. Run key: {run_key}")

    # --- Print Summary Box ---
    print_summary_box(run_key, args.runs_file, run_elo_flag)


if __name__ == "__main__":
    main()
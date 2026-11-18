"""Compare results files: python -m eval.summary eval/results/A.json eval/results/B.json ...

Prints each run's totals and the range over all of them. Use it for before/after: pass the
three "before" files, then the three "after" files, in two calls.
"""
import json
import sys
from pathlib import Path

from eval.run_eval import print_ranges, print_totals
from eval.score import across_runs


def main(paths):
    results = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
    for p, r in zip(paths, results):
        print(f"{Path(p).name}  git {r['git']}{' dirty' if r['dirty'] else ''}  prompt_version {r['prompt_version']}")
        print_totals(r["totals"])
    print_ranges(across_runs(results))
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))

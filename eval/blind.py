"""Blind reader for a translations file: python -m eval.blind eval/results/translations-*.json

Prints only id, run, language and the draft itself, never the drafter's English, the back-translation or the
judge's notes. A reviewer writes their own English reading of each draft first, commits it, and only then opens
the files whole to compare. Identical drafts across runs are printed once, with the runs they came from.
"""
import json
import sys
from pathlib import Path


def blind_drafts(paths):
    """[(id, language, draft, [run labels])], identical drafts merged, in id order."""
    seen = {}
    for p in paths:
        run = Path(p).stem.split("-")[2]          # translations-<stamp>-r<i>-<hash>
        for e in json.loads(Path(p).read_text(encoding="utf-8"))["entries"]:
            seen.setdefault((e["id"], e["language"], e["draft_reply"]), []).append(run)
    return [(i, lang, draft, runs) for (i, lang, draft), runs in sorted(seen.items())]


def main(paths):
    for i, lang, draft, runs in blind_drafts(paths):
        print(f"--- {i} ({lang}) runs {','.join(runs)}\n{draft}\n")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))

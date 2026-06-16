#!/usr/bin/env python3
"""triage.py — summarize a support-message CSV into category/priority counts.

Reads a CSV with columns: id, category, priority, message.
Produces a JSON report containing two breakdowns:
  - "by_category": count of messages per category
  - "by_priority": count of messages per priority
Each breakdown is a list of {name, count} objects sorted by count descending
(ties broken alphabetically for stable, reproducible output).

Standard library only. No hardcoded paths, so it can be scheduled and reused
on any batch of messages.

Usage:
    python triage.py --input support_messages.csv --output report.json

Exit codes:
    0  success
    1  input file missing / unreadable / wrong columns
"""

import argparse
import csv
import json
import sys
from collections import Counter

# Columns the input CSV is required to contain.
REQUIRED_COLUMNS = ["id", "category", "priority", "message"]


def parse_args(argv=None):
    """Define and parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Summarize support messages by category and priority."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to the input CSV (columns: id,category,priority,message).",
    )
    parser.add_argument(
        "--output",
        default="report.json",
        help="Path to write the JSON report (default: report.json).",
    )
    return parser.parse_args(argv)


def sorted_breakdown(counter):
    """Return counter as a list of {name, count} sorted by count desc, then name asc."""
    return [
        {"name": name, "count": count}
        for name, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def build_report(input_path):
    """Read the CSV and return the report dict. Raises on validation failure."""
    with open(input_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)

        # Validate header: every required column must be present.
        header = reader.fieldnames or []
        missing = [col for col in REQUIRED_COLUMNS if col not in header]
        if missing:
            raise ValueError(
                "input is missing required column(s): {}; found: {}".format(
                    ", ".join(missing), ", ".join(header) or "(none)"
                )
            )

        category_counts = Counter()
        priority_counts = Counter()
        total = 0
        for row in reader:
            total += 1
            # Normalize whitespace so " High" and "High" group together.
            category_counts[(row.get("category") or "").strip()] += 1
            priority_counts[(row.get("priority") or "").strip()] += 1

    return {
        "input": input_path,
        "total_messages": total,
        "by_category": sorted_breakdown(category_counts),
        "by_priority": sorted_breakdown(priority_counts),
    }


def main(argv=None):
    args = parse_args(argv)

    try:
        report = build_report(args.input)
    except FileNotFoundError:
        print("error: input file not found: {}".format(args.input), file=sys.stderr)
        return 1
    except OSError as exc:
        print("error: cannot read input: {}".format(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1

    try:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    except OSError as exc:
        print("error: cannot write output: {}".format(exc), file=sys.stderr)
        return 1

    print(
        "wrote {output}: {total} messages, "
        "{ncat} categories, {npri} priorities".format(
            output=args.output,
            total=report["total_messages"],
            ncat=len(report["by_category"]),
            npri=len(report["by_priority"]),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

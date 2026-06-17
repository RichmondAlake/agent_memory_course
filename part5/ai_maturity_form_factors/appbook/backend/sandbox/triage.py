#!/usr/bin/env python3
"""triage.py — summarize a support-message CSV into category/priority counts.

Reads a CSV with columns: id,category,priority,message
Writes a JSON report with two breakdowns — counts per `category` and per
`priority` — each sorted by count descending (ties broken alphabetically).

Standard library only, no hardcoded paths: pass --input/--output so the same
script can be scheduled and reused on any batch.

Usage:
    python triage.py --input support_messages.csv --output report.json

Exit codes:
    0  success
    1  input file missing, unreadable, or missing required columns
"""

import argparse
import csv
import json
import sys
from collections import Counter

# Columns the input CSV must contain (order does not matter).
REQUIRED_COLUMNS = {"id", "category", "priority", "message"}


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Summarize support messages by category and priority."
    )
    parser.add_argument(
        "--input", required=True, help="Path to the input CSV file."
    )
    parser.add_argument(
        "--output",
        default="report.json",
        help="Path to write the JSON report (default: report.json).",
    )
    return parser.parse_args(argv)


def sorted_counts(counter):
    """Return {key: count} ordered by count desc, then key asc for stable ties."""
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return dict(items)


def triage(input_path):
    """Read the CSV and return the report dict. Raises on validation errors."""
    with open(input_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)

        # Validate the header before counting anything.
        header = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - header
        if missing:
            raise ValueError(
                "input is missing required column(s): "
                + ", ".join(sorted(missing))
            )

        categories = Counter()
        priorities = Counter()
        total = 0
        for row in reader:
            categories[row["category"]] += 1
            priorities[row["priority"]] += 1
            total += 1

    return {
        "total_messages": total,
        "by_category": sorted_counts(categories),
        "by_priority": sorted_counts(priorities),
    }


def main(argv=None):
    args = parse_args(argv)
    try:
        report = triage(args.input)
    except FileNotFoundError:
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")

    print(f"Wrote {report['total_messages']} messages summary to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

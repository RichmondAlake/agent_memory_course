"""Execute the Part 7 notebooks end to end and save their outputs in place.

    .venv/bin/python tests/run_notebooks.py --env-file ~/.keys.env               # all notebooks
    .venv/bin/python tests/run_notebooks.py --env-file ~/.keys.env zero_to_hero  # one notebook

Run it with the Python environment that has the requirements installed: the
notebook kernel uses that interpreter. Provider keys come from one or more
--env-file values (only OPENAI_API_KEY, ANTHROPIC_API_KEY, TYPESAFE_API_KEY and the
optional ARIZE_SPACE_ID / ARIZE_API_KEY for tracing are read) or from
the process environment. Oracle must already be running (./oracle.sh start).

Every code cell runs against the real providers and the local database. A
passing run writes the outputs into the notebook itself. A failed run leaves the
notebook unchanged and saves the partial run to the system temporary folder.
Outputs are checked for key values before anything is written.
"""
import argparse
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import nbformat
from dotenv import dotenv_values
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

PART7 = Path(__file__).resolve().parents[1]
KEYS = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TYPESAFE_API_KEY", "ARIZE_SPACE_ID", "ARIZE_API_KEY"]
NOTEBOOKS = {
    "maturity": PART7 / "ai_maturity_form_factors/notebook/ai_maturity_form_factors_notebook.ipynb",
    "zero_to_hero": PART7 / "agent_memory/zero_to_hero/notebook/agent_memory_zero_to_hero.ipynb",
    "maturity_eval": PART7 / "ai_maturity_form_factors/evaluation/notebook/ai_maturity_evaluation.ipynb",
    "memory_eval": PART7 / "agent_memory/evaluation/notebook/agent_memory_evaluation.ipynb",
    "retrieval_benchmark": PART7 / "retrieval_evaluation/notebook/beir_retrieval_benchmark.ipynb",
}
KERNELSPEC = {"name": "python3", "display_name": "Python 3 (ipykernel)", "language": "python"}


def load_keys(env_files):
    for env_file in env_files:
        values = dotenv_values(env_file.expanduser())
        for name in KEYS:
            if values.get(name) and not os.getenv(name):
                os.environ[name] = values[name]
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    return [os.environ[name] for name in KEYS if os.getenv(name)]


def scrub(text, secrets):
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    for value in secrets:
        text = text.replace(value, "[redacted]")
    return text


def execute(path, secrets, timeout):
    notebook = nbformat.read(path, as_version=4)
    notebook.metadata["kernelspec"] = dict(KERNELSPEC)
    client = NotebookClient(
        notebook,
        timeout=timeout,
        kernel_name="python3",
        resources={"metadata": {"path": str(path.parent)}},
    )
    started, error = time.perf_counter(), None
    with client.setup_kernel():
        try:
            for index, cell in enumerate(notebook.cells):
                if cell.cell_type == "code":
                    client.execute_cell(cell, index)
        except CellExecutionError as exc:
            error = scrub(str(exc), secrets)[-4000:]
    notebook.metadata["language_info"].pop("version", None)
    text = nbformat.writes(notebook)
    if any(value in text for value in secrets):
        error = (error or "") + "\nA key value appeared in the outputs; nothing was saved."
        text = scrub(text, secrets)
    executed = sum(1 for c in notebook.cells if c.cell_type == "code" and c.get("execution_count"))
    return text, round(time.perf_counter() - started, 1), executed, error


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="*", help=f"notebooks to run: {', '.join(NOTEBOOKS)} (default: all)")
    parser.add_argument("--env-file", type=Path, action="append", default=[])
    parser.add_argument("--timeout", type=int, default=1800, help="seconds allowed per cell")
    args = parser.parse_args()
    unknown = sorted(set(args.names) - set(NOTEBOOKS))
    if unknown:
        parser.error(f"unknown notebook name(s): {', '.join(unknown)}")
    secrets = load_keys(args.env_file)
    failures = 0
    for name in args.names or NOTEBOOKS:
        path = NOTEBOOKS[name]
        print(f"{name}: running {path.relative_to(PART7)} …", flush=True)
        text, seconds, executed, error = execute(path, secrets, args.timeout)
        if error:
            failures += 1
            partial = Path(tempfile.gettempdir()) / path.name.replace(".ipynb", ".failed.ipynb")
            partial.write_text(text)
            print(f"{name}: FAILED after {seconds}s; partial notebook: {partial}\n{error}")
        else:
            path.write_text(text)
            print(f"{name}: passed in {seconds}s, {executed} code cells; outputs saved in place")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

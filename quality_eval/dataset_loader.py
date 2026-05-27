"""Load HumanEval problems from HuggingFace or a local JSONL file."""

from __future__ import annotations

import json
import os


def load_humaneval(
    num_problems: int | None = None,
    local_path: str | None = None,
) -> list[dict]:
    """Return HumanEval problems as a list of dicts.

    Each dict contains: task_id, prompt, canonical_solution, test, entry_point.

    Args:
        num_problems: cap the number of problems returned (None = all 164).
        local_path: path to a local HumanEval.jsonl file. If provided, skips
                    HuggingFace. Download from:
                    https://github.com/openai/human-eval/blob/master/data/HumanEval.jsonl.gz
    """
    if local_path:
        problems = _load_from_local(local_path)
    else:
        problems = _load_from_huggingface()

    if num_problems is not None:
        problems = problems[:num_problems]

    return problems


def _load_from_huggingface() -> list[dict]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise ImportError(
            "Install the datasets library: pip install datasets\n"
            "Or pass --local-dataset data/HumanEval.jsonl to load from a local file."
        ) from exc

    dataset = load_dataset(
        "openai-community/openai_humaneval",
        split="test",
        trust_remote_code=True,
    )
    return list(dataset)


def _load_from_local(path: str) -> list[dict]:
    """Auto-detect format: directory or file, parquet or jsonl."""
    if os.path.isdir(path):
        return _load_from_parquet(path)
    if path.endswith(".parquet"):
        return _load_from_parquet(path)
    return _load_from_jsonl(path)


def _load_from_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Local dataset not found: {path}")
    problems = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                problems.append(json.loads(line))
    return problems


def _load_from_parquet(path: str) -> list[dict]:
    """Load from a .parquet file or a directory containing parquet files.

    Supports the layout produced by:
        hf download openai/openai_humaneval --repo-type dataset --local-dir ./data/openai_humaneval
    which places the file at:
        data/openai_humaneval/openai_humaneval/test-00000-of-00001.parquet
    """
    if os.path.isdir(path):
        parquet_files = [
            os.path.join(root, f)
            for root, _, files in os.walk(path)
            for f in files
            if f.endswith(".parquet")
        ]
        if not parquet_files:
            raise FileNotFoundError(f"No .parquet files found under {path}")
        parquet_files.sort()
        rows = []
        for pf in parquet_files:
            rows.extend(_read_parquet_file(pf))
        return rows

    return _read_parquet_file(path)


def _read_parquet_file(path: str) -> list[dict]:
    try:
        import pyarrow.parquet as pq
        table = pq.read_table(path)
        return table.to_pylist()
    except ImportError:
        pass

    try:
        import pandas as pd
        return pd.read_parquet(path).to_dict(orient="records")
    except ImportError:
        raise ImportError(
            "Reading parquet files requires pyarrow or pandas.\n"
            "Install with: pip install pyarrow"
        )


def build_instruction_prompt(problem: dict) -> str:
    """Wrap the HumanEval prompt with a completion instruction."""
    return (
        "Complete the following Python function. "
        "Return the complete function including the signature and docstring, "
        "with correct Python indentation. "
        "Do not add explanations. Do not use markdown code blocks.\n\n"
        + problem["prompt"]
    )

"""Extract generated code from LLM responses and run HumanEval tests safely."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile


def extract_code(response_text: str, problem: dict) -> tuple[str, str | None]:
    """Extract executable Python code from an LLM response.

    Returns (full_function_code, error_type_if_extraction_failed).
    full_function_code is ready to be combined with the test block.
    """
    text = response_text.strip()
    entry_point = problem["entry_point"]
    prompt = problem["prompt"]

    # Case 1: markdown code block
    extracted = _extract_markdown_block(text)
    if extracted:
        return _normalize_function(extracted, prompt, entry_point), None

    # Case 2: raw text — model may have repeated the full function or just the body
    return _normalize_function(text, prompt, entry_point), None


def _extract_markdown_block(text: str) -> str | None:
    """Extract code from ```python or ``` fences. Returns None if not found."""
    for fence in ("```python", "```"):
        if fence in text:
            start = text.index(fence) + len(fence)
            remaining = text[start:]
            end = remaining.find("```")
            if end != -1:
                return remaining[:end].strip()
    return None


def _normalize_function(code: str, prompt: str, entry_point: str) -> str:
    """Return a complete function definition ready for execution.

    If the code already contains a def for entry_point, return it as-is.
    Otherwise, prepend the prompt (function signature + docstring) to the body.
    """
    if f"def {entry_point}" in code:
        return code

    # Model returned just the body — prepend the prompt to form a complete function
    prompt_stripped = prompt.rstrip()
    return prompt_stripped + "\n" + _indent_if_needed(code)


def _indent_if_needed(body: str) -> str:
    """Ensure the body has at least 4-space indentation on every non-empty line."""
    lines = body.splitlines()
    indented = []
    for line in lines:
        if line.strip() == "":
            indented.append("")
        elif not line.startswith("    "):
            indented.append("    " + line)
        else:
            indented.append(line)
    return "\n".join(indented)


def build_test_script(function_code: str, problem: dict) -> str:
    """Combine the function, the HumanEval test block, and the check call."""
    entry_point = problem["entry_point"]
    test_block = problem["test"]
    return f"{function_code}\n\n{test_block}\n\ncheck({entry_point})\n"


def run_test(
    function_code: str,
    problem: dict,
    timeout_seconds: int = 10,
) -> tuple[bool, str | None]:
    """Execute the generated function against HumanEval tests.

    Returns (passed, error_message).
    error_message is None on success.
    """
    script = build_test_script(function_code, problem)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(script)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if result.returncode == 0:
            return True, None
        error = (result.stderr or result.stdout or "non-zero exit").strip()
        return False, error[:500]
    except subprocess.TimeoutExpired:
        return False, "execution_timeout"
    except Exception as exc:
        return False, f"runner_error: {exc}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def evaluate_response(response_text: str, problem: dict, timeout_seconds: int = 10) -> dict:
    """Full pipeline: extract code → run tests → return result dict.

    Returns:
        passed: bool
        error_type: None | "extraction_failed" | "execution_error" | "execution_timeout" | "runner_error"
        error_message: str | None
    """
    if not response_text or not response_text.strip():
        return {
            "passed": False,
            "error_type": "extraction_failed",
            "error_message": "empty_response",
        }

    function_code, extraction_error = extract_code(response_text, problem)

    if extraction_error:
        return {
            "passed": False,
            "error_type": "extraction_failed",
            "error_message": extraction_error,
        }

    passed, error_message = run_test(function_code, problem, timeout_seconds)

    if passed:
        return {"passed": True, "error_type": None, "error_message": None}

    error_type = "execution_timeout" if error_message == "execution_timeout" else "execution_error"
    return {
        "passed": False,
        "error_type": error_type,
        "error_message": error_message,
    }

"""HumanEval quality evaluator for the LLM throughput simulator.

Loads HumanEval problems, sends them through the simulator /generate endpoint,
evaluates the generated code against the HumanEval test suite, and writes
quality reports combining pass@1 with latency and cost metrics.

Usage:
    python -m quality_eval.humaneval_runner \\
        --model ollama-llama \\
        --user-id user_vip_01 \\
        --project-id vip_project \\
        --num-problems 20 \\
        --concurrency 2 \\
        --max-tokens 1024

Reports are written to:
    reports/quality_results.csv
    reports/quality_summary.json
    reports/quality_report.md
"""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import Any

import httpx

from quality_eval.code_executor import evaluate_response
from quality_eval.dataset_loader import build_instruction_prompt, load_humaneval
from quality_eval.report_writer import (
    summarize_results,
    write_csv,
    write_json,
    write_markdown,
)

_REPORTS_DIR = "reports"
_POLL_INTERVAL = 0.5
_TERMINAL_STATUSES = {"completed", "failed", "rejected", "timed_out", "not_found"}


async def _poll_until_done(
    client: httpx.AsyncClient,
    base_url: str,
    request_id: str,
    poll_timeout: float,
) -> dict[str, Any]:
    """Poll /requests/{request_id} until a terminal status or timeout."""
    deadline = time.monotonic() + poll_timeout
    while time.monotonic() < deadline:
        try:
            resp = await client.get(f"{base_url}/requests/{request_id}", timeout=10.0)
            data = resp.json()
            if data.get("status") in _TERMINAL_STATUSES:
                return data
        except Exception:
            pass
        await asyncio.sleep(_POLL_INTERVAL)
    return {"request_id": request_id, "status": "timed_out", "message": ""}


async def _evaluate_one(
    client: httpx.AsyncClient,
    base_url: str,
    problem: dict,
    model: str,
    user_id: str,
    project_id: str,
    max_tokens: int,
    poll_timeout: float,
    code_timeout: int,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Send one problem to the simulator and evaluate the response."""
    async with semaphore:
        prompt = build_instruction_prompt(problem)
        payload = {
            "user_id": user_id,
            "project_id": project_id,
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "request_type": "interactive",
        }

        start = time.perf_counter()
        http_status = None
        simulator_status = None
        generated_text = ""
        end_to_end_latency = None

        try:
            resp = await client.post(f"{base_url}/generate", json=payload, timeout=30.0)
            http_status = resp.status_code
            latency = time.perf_counter() - start

            if resp.status_code >= 400:
                return _rejected_result(
                    problem, model, http_status, latency, reason=resp.text[:200]
                )

            data = resp.json()
            simulator_status = data.get("status")
            request_id = data.get("request_id", "")

            if simulator_status == "queued":
                polled = await _poll_until_done(client, base_url, request_id, poll_timeout)
                end_to_end_latency = time.perf_counter() - start
                simulator_status = polled.get("status")
                generated_text = polled.get("message", "")

                if simulator_status != "completed":
                    return _rejected_result(
                        problem, model, http_status, latency,
                        reason=simulator_status, e2e=end_to_end_latency,
                    )
            else:
                generated_text = data.get("message", "")
                end_to_end_latency = latency

        except httpx.TimeoutException:
            latency = time.perf_counter() - start
            return _rejected_result(problem, model, http_status, latency, reason="http_timeout")
        except Exception as exc:
            latency = time.perf_counter() - start
            return _rejected_result(problem, model, http_status, latency, reason=str(exc)[:200])

        eval_result = evaluate_response(generated_text, problem, timeout_seconds=code_timeout)

        return {
            "task_id": problem["task_id"],
            "model": model,
            "passed": eval_result["passed"],
            "http_status": http_status,
            "simulator_status": simulator_status,
            "latency_seconds": round(latency, 4),
            "end_to_end_latency_seconds": round(end_to_end_latency, 4) if end_to_end_latency else None,
            "estimated_input_tokens": data.get("estimated_input_tokens"),
            "estimated_output_tokens": data.get("estimated_output_tokens"),
            "estimated_cost_eur": data.get("estimated_cost_eur"),
            "error_type": eval_result.get("error_type"),
            "error_message": eval_result.get("error_message"),
        }


def _rejected_result(
    problem: dict,
    model: str,
    http_status: int | None,
    latency: float,
    reason: str,
    e2e: float | None = None,
) -> dict:
    return {
        "task_id": problem["task_id"],
        "model": model,
        "passed": False,
        "http_status": http_status,
        "simulator_status": "rejected",
        "latency_seconds": round(latency, 4),
        "end_to_end_latency_seconds": round(e2e, 4) if e2e else None,
        "estimated_input_tokens": None,
        "estimated_output_tokens": None,
        "estimated_cost_eur": None,
        "error_type": "simulator_rejected",
        "error_message": reason,
    }


async def run_evaluation(
    base_url: str,
    model: str,
    user_id: str,
    project_id: str,
    num_problems: int | None,
    concurrency: int,
    max_tokens: int,
    poll_timeout: float,
    code_timeout: int,
    local_dataset: str | None = None,
) -> list[dict]:
    problems = load_humaneval(num_problems, local_path=local_dataset)
    print(f"Loaded {len(problems)} HumanEval problems.")
    print(f"Model: {model} | Concurrency: {concurrency} | max_tokens: {max_tokens}")

    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        tasks = [
            _evaluate_one(
                client=client,
                base_url=base_url,
                problem=p,
                model=model,
                user_id=user_id,
                project_id=project_id,
                max_tokens=max_tokens,
                poll_timeout=poll_timeout,
                code_timeout=code_timeout,
                semaphore=semaphore,
            )
            for p in problems
        ]
        results = []
        for i, coro in enumerate(asyncio.as_completed(tasks), start=1):
            result = await coro
            results.append(result)
            status = "PASS" if result["passed"] else "FAIL"
            print(f"  [{i:>3}/{len(problems)}] {result['task_id']} — {status}"
                  f" | latency={result['latency_seconds']}s"
                  f" | error={result.get('error_type')}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="HumanEval quality evaluator")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="ollama-llama")
    parser.add_argument("--user-id", default="user_vip_01")
    parser.add_argument("--project-id", default="vip_project")
    parser.add_argument("--num-problems", type=int, default=20,
                        help="Number of HumanEval problems to evaluate (default: 20, max: 164)")
    parser.add_argument("--concurrency", type=int, default=2,
                        help="Max concurrent requests to the simulator (default: 2)")
    parser.add_argument("--max-tokens", type=int, default=1024,
                        help="Max tokens for code generation (default: 1024)")
    parser.add_argument("--poll-timeout", type=float, default=120.0,
                        help="Seconds to poll a queued request before giving up (default: 120)")
    parser.add_argument("--code-timeout", type=int, default=10,
                        help="Seconds to allow generated code to run before timeout (default: 10)")
    parser.add_argument("--local-dataset", default=None,
                        help="Path to a local HumanEval.jsonl file (skips HuggingFace download)")
    args = parser.parse_args()

    results = asyncio.run(
        run_evaluation(
            base_url=args.base_url,
            model=args.model,
            user_id=args.user_id,
            project_id=args.project_id,
            num_problems=args.num_problems,
            concurrency=args.concurrency,
            max_tokens=args.max_tokens,
            poll_timeout=args.poll_timeout,
            code_timeout=args.code_timeout,
            local_dataset=args.local_dataset,
        )
    )

    summary = summarize_results(results)

    csv_path = f"{_REPORTS_DIR}/quality_results.csv"
    json_path = f"{_REPORTS_DIR}/quality_summary.json"
    md_path = f"{_REPORTS_DIR}/quality_report.md"

    write_csv(results, csv_path)
    write_json(summary, json_path)
    write_markdown(summary, md_path)

    print(f"\n--- Results for {args.model} ---")
    print(f"  pass@1 : {summary['pass_at_1']:.1%}  ({summary['passed']}/{summary['total_problems']})")
    print(f"  P95 latency : {summary.get('p95_latency_seconds')}s")
    print(f"  Total cost  : €{summary.get('total_cost_eur', 0.0):.6f}")
    if summary.get("cost_per_passed_problem_eur") is not None:
        print(f"  Cost/passed : €{summary['cost_per_passed_problem_eur']:.6f}")
    print(f"\nReports written to:")
    print(f"  {csv_path}")
    print(f"  {json_path}")
    print(f"  {md_path}")


if __name__ == "__main__":
    main()

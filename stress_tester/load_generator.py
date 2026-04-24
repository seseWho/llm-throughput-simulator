import argparse
import asyncio
import random
import time
from pathlib import Path
from typing import Any

import httpx

from stress_tester.report_writer import (
    summarize_results,
    write_comparison_markdown,
    write_csv,
    write_json,
)
from stress_tester.scenarios import get_scenario, list_scenarios

USER_PROJECTS = {
    "user_standard_01": "standard_project",
    "user_vip_01": "vip_project",
    "user_batch_01": "batch_project",
    "admin_01": "vip_project",
}

PROMPT_SIZES = {
    "short": "Summarize this request briefly.",
    "medium": "Write a concise explanation of how queueing and priority affect LLM serving latency.",
    "long": (
        "Analyze an LLM serving system under heavy concurrent traffic. "
        "Discuss admission control, priority scheduling, queue limits, quotas, "
        "cost tracking, latency, and graceful degradation."
    ),
}


async def run_load(
    backend_base_url: str,
    scenario_name: str,
    timeout_seconds: float = 30.0,
    poll_queued: bool = True,
    poll_interval: float = 0.2,
    poll_timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """Run an async load scenario against the backend."""
    scenario = get_scenario(scenario_name)
    semaphore = asyncio.Semaphore(int(scenario["concurrency"]))
    results: list[dict[str, Any]] = []
    base_url = backend_base_url.rstrip("/")

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds) as client:
        tasks = []
        for request_index in range(int(scenario["total_requests"])):
            tasks.append(
                asyncio.create_task(
                    _send_one_request(
                        client,
                        semaphore,
                        scenario,
                        request_index,
                        poll_queued=poll_queued,
                        poll_interval=poll_interval,
                        poll_timeout=poll_timeout,
                    )
                )
            )
            delay = float(scenario.get("delay_between_requests_seconds", 0))
            if delay > 0:
                await asyncio.sleep(delay)

        for task in asyncio.as_completed(tasks):
            results.append(await task)

    return sorted(results, key=lambda result: result["request_index"])


async def _send_one_request(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    scenario: dict,
    request_index: int,
    poll_queued: bool = True,
    poll_interval: float = 0.2,
    poll_timeout: float = 30.0,
) -> dict[str, Any]:
    async with semaphore:
        user_id = random.choice(scenario["users"])
        model = random.choice(scenario["models"])
        request_type = _weighted_choice(scenario["request_type_distribution"])
        prompt_size = _weighted_choice(scenario["prompt_size_distribution"])
        project_id = USER_PROJECTS[user_id]
        payload = {
            "user_id": user_id,
            "project_id": project_id,
            "model": model,
            "prompt": PROMPT_SIZES[prompt_size],
            "max_tokens": 64,
            "request_type": request_type,
        }

        start_time = time.perf_counter()
        result = {
            "request_index": request_index,
            "user_id": user_id,
            "project_id": project_id,
            "model": model,
            "backend_name": _infer_backend_name(model),
            "request_type": request_type,
            "http_status": None,
            "backend_status": None,
            "request_id": None,
            "latency_seconds": None,
            "final_backend_status": None,
            "final_latency_seconds": None,
            "end_to_end_latency_seconds": None,
            "polling_attempts": 0,
            "polling_error": None,
            "error": None,
        }

        try:
            response = await client.post("/generate", json=payload)
            result["latency_seconds"] = time.perf_counter() - start_time
            result["http_status"] = response.status_code

            try:
                data = response.json()
            except ValueError:
                data = {}

            result["backend_status"] = data.get("status")
            result["backend_name"] = data.get("backend_name") or result["backend_name"]
            result["request_id"] = data.get("request_id")
            result["final_backend_status"] = result["backend_status"]
            result["final_latency_seconds"] = result["latency_seconds"]
            result["end_to_end_latency_seconds"] = result["latency_seconds"]
            if response.status_code >= 400:
                result["error"] = data.get("detail") or response.text

            if (
                poll_queued
                and result["backend_status"] == "queued"
                and result["request_id"]
            ):
                poll_result = await poll_request_status(
                    client=client,
                    request_id=str(result["request_id"]),
                    initial_start_time=start_time,
                    poll_interval=poll_interval,
                    poll_timeout=poll_timeout,
                )
                result.update(poll_result)
        except Exception as exc:
            result["latency_seconds"] = time.perf_counter() - start_time
            result["end_to_end_latency_seconds"] = result["latency_seconds"]
            result["error"] = str(exc)

        return result


async def poll_request_status(
    client: httpx.AsyncClient,
    request_id: str,
    initial_start_time: float,
    poll_interval: float,
    poll_timeout: float,
) -> dict[str, Any]:
    """Poll a queued request until terminal status or timeout."""
    terminal_statuses = {"completed", "failed", "rejected"}
    poll_start = time.perf_counter()
    attempts = 0

    while time.perf_counter() - poll_start < poll_timeout:
        attempts += 1
        try:
            response = await client.get(f"/requests/{request_id}")
            data = response.json()
            status = data.get("status")
            if status in terminal_statuses:
                now = time.perf_counter()
                return {
                    "final_backend_status": status,
                    "final_latency_seconds": now - poll_start,
                    "end_to_end_latency_seconds": now - initial_start_time,
                    "polling_attempts": attempts,
                    "polling_error": None,
                }
        except Exception as exc:
            return {
                "final_backend_status": "failed",
                "final_latency_seconds": time.perf_counter() - poll_start,
                "end_to_end_latency_seconds": time.perf_counter() - initial_start_time,
                "polling_attempts": attempts,
                "polling_error": str(exc),
            }

        await asyncio.sleep(poll_interval)

    now = time.perf_counter()
    return {
        "final_backend_status": "timed_out",
        "final_latency_seconds": now - poll_start,
        "end_to_end_latency_seconds": now - initial_start_time,
        "polling_attempts": attempts,
        "polling_error": "poll_timeout",
    }


def _weighted_choice(distribution: dict[str, float]) -> str:
    names = list(distribution.keys())
    weights = list(distribution.values())
    return random.choices(names, weights=weights, k=1)[0]


def _infer_backend_name(model: str) -> str:
    if model.startswith("simulated"):
        return "simulated"
    if model.startswith("ollama"):
        return "ollama"
    return "unknown"


async def _run_cli(args: argparse.Namespace) -> None:
    results = await run_load(
        args.base_url,
        args.scenario,
        poll_queued=_parse_bool(args.poll_queued),
        poll_interval=args.poll_interval,
        poll_timeout=args.poll_timeout,
    )
    summary = summarize_results(results)

    reports_dir = Path("reports")
    write_csv(results, str(reports_dir / "latest_results.csv"))
    write_json(summary, str(reports_dir / "latest_summary.json"))
    write_comparison_markdown(summary, str(reports_dir / "latest_comparison.md"))

    print(f"Scenario: {args.scenario}")
    print(f"Total requests: {summary['total_requests']}")
    print(f"Successful HTTP requests: {summary['successful_http_requests']}")
    print(f"Failed HTTP requests: {summary['failed_http_requests']}")
    print(
        "Reports written to reports/latest_results.csv, "
        "reports/latest_summary.json and reports/latest_comparison.md"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an async LLM load scenario.")
    parser.add_argument("--base-url", required=True, help="Backend base URL.")
    parser.add_argument(
        "--scenario",
        required=True,
        choices=list_scenarios(),
        help="Scenario name.",
    )
    parser.add_argument(
        "--poll-queued",
        default="true",
        choices=["true", "false"],
        help="Poll queued requests until terminal status.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.2,
        help="Seconds between queued request polling attempts.",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=30.0,
        help="Maximum seconds to poll each queued request.",
    )
    args = parser.parse_args()
    asyncio.run(_run_cli(args))


def _parse_bool(value: str) -> bool:
    return value.lower() == "true"


if __name__ == "__main__":
    main()

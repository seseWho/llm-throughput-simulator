import argparse
import asyncio
import random
import time
from pathlib import Path
from typing import Any

import httpx

from stress_tester.report_writer import summarize_results, write_csv, write_json
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
                    _send_one_request(client, semaphore, scenario, request_index)
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
            "request_type": request_type,
            "http_status": None,
            "backend_status": None,
            "request_id": None,
            "latency_seconds": None,
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
            result["request_id"] = data.get("request_id")
            if response.status_code >= 400:
                result["error"] = data.get("detail") or response.text
        except Exception as exc:
            result["latency_seconds"] = time.perf_counter() - start_time
            result["error"] = str(exc)

        return result


def _weighted_choice(distribution: dict[str, float]) -> str:
    names = list(distribution.keys())
    weights = list(distribution.values())
    return random.choices(names, weights=weights, k=1)[0]


async def _run_cli(args: argparse.Namespace) -> None:
    results = await run_load(args.base_url, args.scenario)
    summary = summarize_results(results)

    reports_dir = Path("reports")
    write_csv(results, str(reports_dir / "latest_results.csv"))
    write_json(summary, str(reports_dir / "latest_summary.json"))

    print(f"Scenario: {args.scenario}")
    print(f"Total requests: {summary['total_requests']}")
    print(f"Successful HTTP requests: {summary['successful_http_requests']}")
    print(f"Failed HTTP requests: {summary['failed_http_requests']}")
    print("Reports written to reports/latest_results.csv and reports/latest_summary.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an async LLM load scenario.")
    parser.add_argument("--base-url", required=True, help="Backend base URL.")
    parser.add_argument(
        "--scenario",
        required=True,
        choices=list_scenarios(),
        help="Scenario name.",
    )
    args = parser.parse_args()
    asyncio.run(_run_cli(args))


if __name__ == "__main__":
    main()

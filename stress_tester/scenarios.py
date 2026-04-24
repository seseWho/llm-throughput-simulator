SCENARIOS: dict[str, dict] = {
    "normal_load": {
        "name": "normal_load",
        "description": "Steady standard-user traffic against the small simulated model.",
        "total_requests": 100,
        "concurrency": 10,
        "users": ["user_standard_01"],
        "models": ["simulated-small"],
        "request_type_distribution": {
            "interactive": 1.0,
        },
        "prompt_size_distribution": {
            "short": 0.8,
            "medium": 0.2,
        },
        "delay_between_requests_seconds": 0.01,
    },
    "burst_load": {
        "name": "burst_load",
        "description": "Short burst of concurrent standard-user traffic.",
        "total_requests": 200,
        "concurrency": 50,
        "users": ["user_standard_01"],
        "models": ["simulated-small", "simulated-large"],
        "request_type_distribution": {
            "interactive": 1.0,
        },
        "prompt_size_distribution": {
            "short": 0.5,
            "medium": 0.4,
            "long": 0.1,
        },
        "delay_between_requests_seconds": 0.0,
    },
    "vip_protection": {
        "name": "vip_protection",
        "description": "Mixed standard and VIP traffic to observe priority behavior.",
        "total_requests": 150,
        "concurrency": 30,
        "users": ["user_standard_01", "user_vip_01"],
        "models": ["simulated-small"],
        "request_type_distribution": {
            "interactive": 1.0,
        },
        "prompt_size_distribution": {
            "short": 0.7,
            "medium": 0.3,
        },
        "delay_between_requests_seconds": 0.005,
    },
    "abusive_user": {
        "name": "abusive_user",
        "description": "High-frequency single standard user traffic to exercise rate limiting.",
        "total_requests": 300,
        "concurrency": 75,
        "users": ["user_standard_01"],
        "models": ["simulated-small"],
        "request_type_distribution": {
            "interactive": 1.0,
        },
        "prompt_size_distribution": {
            "short": 1.0,
        },
        "delay_between_requests_seconds": 0.0,
    },
    "mixed_load": {
        "name": "mixed_load",
        "description": "Mixed users, request types, prompt sizes, and simulated models.",
        "total_requests": 250,
        "concurrency": 40,
        "users": ["user_standard_01", "user_vip_01", "user_batch_01"],
        "models": ["simulated-small", "simulated-large"],
        "request_type_distribution": {
            "interactive": 0.7,
            "batch": 0.3,
        },
        "prompt_size_distribution": {
            "short": 0.5,
            "medium": 0.35,
            "long": 0.15,
        },
        "delay_between_requests_seconds": 0.005,
    },
}


def get_scenario(name: str) -> dict:
    """Return a scenario by name."""
    try:
        return SCENARIOS[name]
    except KeyError as exc:
        available = ", ".join(sorted(SCENARIOS))
        raise ValueError(f"Unknown scenario '{name}'. Available scenarios: {available}") from exc


def list_scenarios() -> list[str]:
    """Return available scenario names."""
    return sorted(SCENARIOS)

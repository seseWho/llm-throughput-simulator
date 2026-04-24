class AdmissionController:
    """Decide whether a request can run now, wait in queue, or be rejected."""

    def decide(
        self,
        queue_size: int,
        active_requests: int,
        limits_config: dict,
        project_priority: str,
        request_type: str,
    ) -> dict[str, object]:
        """Return an admission decision for the current service state."""
        global_limits = limits_config.get("global_limits", {})
        max_active_requests = int(global_limits.get("max_active_requests", 0))
        max_queue_size = int(global_limits.get("max_queue_size", 0))

        if active_requests < max_active_requests:
            return {
                "admitted": True,
                "decision": "accept",
                "reason": "capacity_available",
            }

        if queue_size < max_queue_size:
            return {
                "admitted": True,
                "decision": "queue",
                "reason": "active_capacity_full",
            }

        return {
            "admitted": False,
            "decision": "reject",
            "reason": "queue_full",
        }

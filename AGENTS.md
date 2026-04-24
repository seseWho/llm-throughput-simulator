# Project Instructions

This project is a Python MVP for an LLM high-throughput serving simulator.

## Goal
Validate a backend architecture for managing thousands of LLM requests using:
- admission control
- priority queues
- rate limiting
- quota management
- cost tracking
- simulated LLM backend
- later Ollama integration

## Current phase
Build incrementally. Do not over-engineer.

## Technology
- Python 3.11+
- FastAPI
- asyncio
- httpx
- PyYAML
- pydantic
- pytest

## Rules
- Keep modules small and testable.
- Do not implement production complexity unless requested.
- Prefer clear interfaces over clever abstractions.
- Do not connect to Ollama until explicitly requested.
- Do not implement stress testing until explicitly requested.
- Every new feature should include at least one basic test.
- Configuration should remain externalized in YAML files.
- Business rules should not be hardcoded if they belong in config.

## Architecture references
Read:
- docs/requirements.md
- docs/architecture.md
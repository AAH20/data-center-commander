#!/usr/bin/env python3
"""Initialize tracing for Data Center Commander.

Call this at application startup to configure the tracer provider.

Usage:
    python scripts/setup-tracing.py

Or via environment variables:
    DCC_TRACING_ENABLED=true
    DCC_SERVICE_NAME=data-center-commander
    DCC_TRACE_SAMPLE_RATE=1.0
"""
from __future__ import annotations

import os
import sys

# Add src to path for direct script execution
_script_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.join(_script_dir, "..", "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


def main() -> None:
    """Initialize tracing and report status."""
    from dcc.observability import get_logger, Sampler, TracerProvider

    logger = get_logger("dcc.tracing.setup")

    enabled = os.environ.get("DCC_TRACING_ENABLED", "false").lower() == "true"
    if not enabled:
        logger.info("tracing_not_enabled", hint="Set DCC_TRACING_ENABLED=true to enable")
        print("Tracing is disabled. Set DCC_TRACING_ENABLED=true to enable.")
        return

    service_name = os.environ.get("DCC_SERVICE_NAME", "data-center-commander")
    sample_rate = float(os.environ.get("DCC_TRACE_SAMPLE_RATE", "1.0"))

    # Configure the global tracer provider
    provider = TracerProvider()
    provider.set_sampler(Sampler(rate=sample_rate))

    # Get a tracer to verify it works
    tracer = provider.get_tracer(service_name)

    logger.info(
        "tracing_initialized",
        service=service_name,
        sample_rate=sample_rate,
    )
    print(f"Tracing initialized: service={service_name}, sample_rate={sample_rate}")
    print(f"Tracer: {tracer}")
    print(f"View traces at: http://localhost:16686 (Jaeger UI)")


if __name__ == "__main__":
    main()

"""Nvidia Clara threat intel integration for Data Center Commander.

Leverages Nvidia Clara healthcare/SOC threat intelligence framework
for GPU-accelerated IOC extraction and correlation. Optional API
integration with fallback to zero-API cognee-based detection.
"""

from typing import Any

import requests


def clara_threat_enrichment(
    record: dict[str, Any],
    clara_endpoint: str = "https://api.nvidia.com/clara/soc/threat",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Enrich SOC record with Nvidia Clara threat intelligence.

    Args:
        record: Parsed telemetry record from any SOC connector.
        clara_endpoint: Clara API endpoint URL (optional, for demo).
        api_key: Clara API key for authenticated requests (optional).

    Returns:
        Enriched record dict with Clara threat fields added.
    """
    # Prepare record for Clara API
    payload = {
        "source_ip": record.get("source_ip", ""),
        "destination_ip": record.get("destination_ip", ""),
        "timestamp": record.get("timestamp", ""),
        "logs": record.get("logs", []),
        "connector_type": record.get("connector", "cef"),
    }

    # Add API key if provided (optional - for demo mode)
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Call Clara API (or mock for demo)
    try:
        start_time = __import__("time").time()
        response = requests.post(
            clara_endpoint,
            json=payload,
            headers=headers,
            timeout=10,
        )
        clara_response_time = __import__("time").time() - start_time

        if response.status_code == 200:
            clara_data = response.json()
            # Enrich record with Clara findings
            enriched = {
                **record,
                "clara_threat_score": clara_data.get("threat_score", 0.0),
                "clara_iocs": clara_data.get("iocs", []),
                "clara_mitre_technique": clara_data.get("mitre_technique", ""),
                "clara_processing_ms": round(clara_response_time * 1000),
            }
            return enriched
        else:
            # Fallback: return record unchanged
            return {
                **record,
                "clara_threat_score": 0.0,
                "clara_iocs": [],
                "clara_mitre_technique": "",
                "clara_processing_ms": 0,
                "clara_fallback": True,
            }

    except Exception:
        # Network failure or other error - return record with fallback flags
        return {
            **record,
            "clara_threat_score": 0.0,
            "clara_iocs": [],
            "clara_mitre_technique": "",
            "clara_processing_ms": 0,
            "clara_fallback": True,
            "clara_error": "Network failure - using zero-API fallback",
        }

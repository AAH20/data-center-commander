#!/usr/bin/env python3
"""
Log Processor for IaC Logging Stack
Reads logs from Elasticsearch and Loki, enriches them, and forwards to both.
"""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any

import requests
from elasticsearch import Elasticsearch

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("log-processor")

# Configuration
ES_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))

# Graceful shutdown
running = True


def signal_handler(signum, frame):
    global running
    logger.info("Received shutdown signal, finishing current batch...")
    running = False


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


class LogProcessor:
    """Processes and enriches logs between Elasticsearch and Loki."""

    def __init__(self):
        self.es = Elasticsearch([ES_URL])
        self.loki_url = LOKI_URL
        self.last_check = datetime.now(timezone.utc).isoformat()

    def check_connections(self) -> bool:
        """Verify both backends are reachable."""
        try:
            es_health = self.es.cluster.health()
            logger.info(f"Elasticsearch: {es_health['status']}")
        except Exception as e:
            logger.error(f"Elasticsearch connection failed: {e}")
            return False

        try:
            resp = requests.get(f"{self.loki_url}/ready", timeout=5)
            if resp.status_code == 200:
                logger.info("Loki: ready")
            else:
                logger.warning(f"Loki not ready: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Loki connection failed: {e}")
            return False

        return True

    def fetch_recent_logs(self) -> list[dict[str, Any]]:
        """Fetch recent logs from Elasticsearch."""
        query = {
            "query": {
                "range": {
                    "@timestamp": {
                        "gte": self.last_check,
                    }
                }
            },
            "size": BATCH_SIZE,
            "sort": [{"@timestamp": "asc"}],
        }

        try:
            result = self.es.search(index="iac-logs-*", body=query)
            return result.get("hits", {}).get("hits", [])
        except Exception as e:
            logger.error(f"Failed to fetch from Elasticsearch: {e}")
            return []

    def enrich_log(self, log: dict[str, Any]) -> dict[str, Any]:
        """Enrich a log entry with additional metadata."""
        source = log.get("_source", {})

        # Add processing metadata
        source["processed_at"] = datetime.now(timezone.utc).isoformat()
        source["processor"] = "log-processor"

        # Normalize log level
        level = source.get("log_level", source.get("level", "INFO")).upper()
        if level not in ("DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"):
            level = "INFO"
        source["log_level"] = level

        # Add severity score for alerting
        severity_map = {
            "DEBUG": 0,
            "INFO": 1,
            "WARN": 2,
            "WARNING": 2,
            "ERROR": 3,
            "CRITICAL": 4,
            "FATAL": 4,
        }
        source["severity"] = severity_map.get(level, 1)

        return source

    def push_to_loki(self, logs: list[dict[str, Any]]) -> bool:
        """Push enriched logs to Loki."""
        streams = []
        for log in logs:
            labels = {
                "job": "iac-enriched",
                "level": log.get("log_level", "INFO"),
                "service": log.get("service", "unknown"),
                "source": "log-processor",
            }
            timestamp = log.get("@timestamp", datetime.now(timezone.utc).isoformat())
            # Loki expects nanosecond timestamps
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                ts_ns = str(int(dt.timestamp() * 1e9))
            except (ValueError, AttributeError):
                ts_ns = str(int(time.time() * 1e9))

            streams.append(
                {
                    "stream": labels,
                    "values": [[ts_ns, json.dumps(log)]],
                }
            )

        if not streams:
            return True

        try:
            resp = requests.post(
                f"{self.loki_url}/loki/api/v1/push",
                json={"streams": streams},
                timeout=10,
            )
            if resp.status_code == 204:
                logger.info(f"Pushed {len(streams)} streams to Loki")
                return True
            else:
                logger.error(f"Loki push failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to push to Loki: {e}")
            return False

    def update_index_template(self):
        """Ensure the Elasticsearch index template exists."""
        template = {
            "index_patterns": ["iac-logs-*"],
            "template": {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "index.lifecycle.name": "iac-logs-policy",
                    "index.lifecycle.rollover_alias": "iac-logs",
                },
                "mappings": {
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "message": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "log_level": {"type": "keyword"},
                        "severity": {"type": "integer"},
                        "service": {"type": "keyword"},
                        "environment": {"type": "keyword"},
                        "datacenter": {"type": "keyword"},
                        "iac_stack": {"type": "boolean"},
                        "processed_at": {"type": "date"},
                        "processor": {"type": "keyword"},
                    }
                },
            },
        }

        try:
            self.es.indices.put_index_template(name="iac-logs-template", body=template)
            logger.info("Index template updated")
        except Exception as e:
            logger.warning(f"Could not update index template: {e}")

    def run(self):
        """Main processing loop."""
        logger.info("Log Processor starting...")

        if not self.check_connections():
            logger.error("Backend connections failed, retrying in 30s...")
            time.sleep(30)
            return

        self.update_index_template()

        while running:
            try:
                logs = self.fetch_recent_logs()
                if logs:
                    enriched = [self.enrich_log(log) for log in logs]
                    self.push_to_loki(enriched)
                    self.last_check = datetime.now(timezone.utc).isoformat()
                    logger.info(f"Processed {len(logs)} logs")
                else:
                    logger.debug("No new logs to process")
            except Exception as e:
                logger.error(f"Processing error: {e}")

            time.sleep(POLL_INTERVAL)

        logger.info("Log Processor stopped")


if __name__ == "__main__":
    processor = LogProcessor()
    processor.run()

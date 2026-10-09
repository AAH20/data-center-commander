"""Threat intelligence feed management and IOC matching for Metron.

Provides feed fetching, parsing, caching, and real-time IOC matching
against Metron-enriched telemetry.
"""

import csv
import hashlib
import ipaddress
import json
import logging
import os
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.request import urlopen, Request

logger = logging.getLogger(__name__)


class IOCEntry:
    """Represents a single Indicator of Compromise."""

    def __init__(self, value: str, ioc_type: str, feed_name: str,
                 confidence: str = "medium", category: str = "",
                 first_seen: Optional[str] = None):
        self.value = value
        self.ioc_type = ioc_type
        self.feed_name = feed_name
        self.confidence = confidence
        self.category = category
        self.first_seen = first_seen or datetime.now(timezone.utc).isoformat()
        self.last_seen = self.first_seen
        self.hit_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "ioc_type": self.ioc_type,
            "feed_name": self.feed_name,
            "confidence": self.confidence,
            "category": self.category,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "hit_count": self.hit_count,
        }


class ThreatIntelFeed:
    """Manages a single threat intelligence feed."""

    def __init__(self, feed_config: Dict[str, Any]):
        self.id = feed_config["id"]
        self.name = feed_config["name"]
        self.url = feed_config["url"]
        self.feed_type = feed_config["type"]
        self.format = feed_config["format"]
        self.update_interval_hours = feed_config.get("update_interval_hours", 24)
        self.confidence = feed_config.get("confidence", "medium")
        self.category = feed_config.get("category", "")
        self._iocs: Dict[str, IOCEntry] = {}
        self._last_update: Optional[datetime] = None
        self._cache_file = os.path.join(
            os.path.dirname(__file__), f".cache_{self.id}.json"
        )

    @property
    def ioc_count(self) -> int:
        return len(self._iocs)

    @property
    def last_update(self) -> Optional[datetime]:
        return self._last_update

    def needs_update(self) -> bool:
        if self._last_update is None:
            return True
        elapsed = datetime.now(timezone.utc) - self._last_update
        return elapsed > timedelta(hours=self.update_interval_hours)

    def fetch(self) -> bool:
        """Fetch and parse the feed. Returns True on success."""
        try:
            req = Request(self.url, headers={"User-Agent": "DCC-Metron-TI/1.0"})
            with urlopen(req, timeout=30) as resp:
                data = resp.read()

            if self.format == "json":
                self._parse_json(data)
            elif self.format == "csv":
                self._parse_csv(data)
            elif self.format == "plain_text":
                self._parse_plain_text(data)
            elif self.format == "hosts_file":
                self._parse_hosts_file(data)
            else:
                logger.warning("Unknown feed format: %s", self.format)
                return False

            self._last_update = datetime.now(timezone.utc)
            self._save_cache()
            logger.info("Feed '%s' updated: %d IOCs", self.name, self.ioc_count)
            return True

        except Exception as e:
            logger.error("Failed to fetch feed '%s': %s", self.name, e)
            return False

    def _parse_json(self, data: bytes) -> None:
        items = json.loads(data)
        if isinstance(items, dict):
            items = items.get("data", items.get("results", [items]))
        for item in items:
            if isinstance(item, dict):
                value = item.get("ip", item.get("domain", item.get("url", item.get("hash", ""))))
                if value:
                    self._add_ioc(str(value))

    def _parse_csv(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        reader = csv.reader(text.splitlines())
        for row in reader:
            if row and not row[0].startswith("#"):
                self._add_ioc(row[0].strip())

    def _parse_plain_text(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                self._add_ioc(line)

    def _parse_hosts_file(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 2:
                    self._add_ioc(parts[1].strip())

    def _add_ioc(self, value: str) -> None:
        if value and value not in self._iocs:
            self._iocs[value] = IOCEntry(
                value=value,
                ioc_type=self.feed_type,
                feed_name=self.name,
                confidence=self.confidence,
                category=self.category,
            )

    def match(self, value: str) -> Optional[IOCEntry]:
        """Check if a value matches any IOC in this feed."""
        entry = self._iocs.get(value)
        if entry:
            entry.hit_count += 1
            entry.last_seen = datetime.now(timezone.utc).isoformat()
            return entry

        # For IP blocklists, check CIDR membership
        if self.feed_type == "ip_blocklist":
            try:
                addr = ipaddress.ip_address(value)
                for ioc_val, ioc_entry in self._iocs.items():
                    try:
                        network = ipaddress.ip_network(ioc_val, strict=False)
                        if addr in network:
                            ioc_entry.hit_count += 1
                            ioc_entry.last_seen = datetime.now(timezone.utc).isoformat()
                            return ioc_entry
                    except ValueError:
                        continue
            except ValueError:
                pass

        return None

    def _save_cache(self) -> None:
        try:
            cache_data = {
                "last_update": self._last_update.isoformat() if self._last_update else None,
                "iocs": {k: v.to_dict() for k, v in self._iocs.items()},
            }
            with open(self._cache_file, "w") as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.warning("Failed to save cache for feed '%s': %s", self.name, e)

    def load_cache(self) -> bool:
        """Load cached IOCs from disk. Returns True on success."""
        try:
            if not os.path.exists(self._cache_file):
                return False
            with open(self._cache_file, "r") as f:
                cache_data = json.load(f)
            for value, data in cache_data.get("iocs", {}).items():
                entry = IOCEntry(
                    value=data["value"],
                    ioc_type=data["ioc_type"],
                    feed_name=data["feed_name"],
                    confidence=data["confidence"],
                    category=data["category"],
                    first_seen=data.get("first_seen"),
                )
                entry.hit_count = data.get("hit_count", 0)
                entry.last_seen = data.get("last_seen")
                self._iocs[value] = entry
            if cache_data.get("last_update"):
                self._last_update = datetime.fromisoformat(cache_data["last_update"])
            logger.info("Loaded %d cached IOCs for feed '%s'", self.ioc_count, self.name)
            return True
        except Exception as e:
            logger.warning("Failed to load cache for feed '%s': %s", self.name, e)
            return False


class ThreatIntelManager:
    """Manages all threat intelligence feeds and performs IOC matching."""

    def __init__(self, feeds_config_path: Optional[str] = None):
        if feeds_config_path is None:
            feeds_config_path = os.path.join(
                os.path.dirname(__file__), "threat_intel_feeds.json"
            )
        self._feeds: Dict[str, ThreatIntelFeed] = {}
        self._load_feeds(feeds_config_path)

    def _load_feeds(self, config_path: str) -> None:
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            for feed_config in config.get("feeds", []):
                feed = ThreatIntelFeed(feed_config)
                feed.load_cache()
                self._feeds[feed.id] = feed
            logger.info("Loaded %d threat intel feeds", len(self._feeds))
        except Exception as e:
            logger.error("Failed to load threat intel feeds: %s", e)

    def update_all_feeds(self) -> Dict[str, bool]:
        """Update all feeds that need refreshing."""
        results = {}
        for feed_id, feed in self._feeds.items():
            if feed.needs_update():
                results[feed_id] = feed.fetch()
            else:
                results[feed_id] = True
        return results

    def match_ip(self, ip: str) -> List[IOCEntry]:
        """Match an IP address against all feeds."""
        matches = []
        for feed in self._feeds.values():
            if feed.feed_type == "ip_blocklist":
                entry = feed.match(ip)
                if entry:
                    matches.append(entry)
        return matches

    def match_domain(self, domain: str) -> List[IOCEntry]:
        """Match a domain against all feeds."""
        matches = []
        for feed in self._feeds.values():
            if feed.feed_type in ("domain_blocklist", "url_blocklist"):
                entry = feed.match(domain)
                if entry:
                    matches.append(entry)
        return matches

    def match_url(self, url: str) -> List[IOCEntry]:
        """Match a URL against all feeds."""
        matches = []
        for feed in self._feeds.values():
            if feed.feed_type == "url_blocklist":
                entry = feed.match(url)
                if entry:
                    matches.append(entry)
        return matches

    def match_record(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Match a telemetry record against all feeds. Returns list of matches."""
        matches = []

        # Extract IPs from record
        ip_fields = ["srcaddr", "dstaddr", "source_ip", "destination_ip", "src_ip", "dst_ip"]
        for field in ip_fields:
            ip = record.get(field, "")
            if ip:
                for entry in self.match_ip(ip):
                    matches.append({
                        "field": field,
                        "value": ip,
                        "ioc": entry.to_dict(),
                        "match_type": "ip",
                    })

        # Extract domains/URLs from record
        domain_fields = ["request", "referer", "uri_stem", "host", "domain"]
        for field in domain_fields:
            value = record.get(field, "")
            if value:
                for entry in self.match_domain(value):
                    matches.append({
                        "field": field,
                        "value": value,
                        "ioc": entry.to_dict(),
                        "match_type": "domain",
                    })
                for entry in self.match_url(value):
                    matches.append({
                        "field": field,
                        "value": value,
                        "ioc": entry.to_dict(),
                        "match_type": "url",
                    })

        return matches

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about all feeds."""
        return {
            "total_feeds": len(self._feeds),
            "total_iocs": sum(f.ioc_count for f in self._feeds.values()),
            "feeds": [
                {
                    "id": f.id,
                    "name": f.name,
                    "ioc_count": f.ioc_count,
                    "last_update": f.last_update.isoformat() if f.last_update else None,
                    "needs_update": f.needs_update(),
                }
                for f in self._feeds.values()
            ],
        }

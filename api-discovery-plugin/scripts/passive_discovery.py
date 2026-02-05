#!/usr/bin/env python3
"""
Passive API Discovery

Discovers APIs through passive analysis without making active network requests:
- Access log analysis (nginx, Apache, API Gateway)
- Configuration file scanning
- DNS record analysis
- Service catalog/CMDB integration

Usage:
    python passive_discovery.py --log-dir /var/log/nginx/ --output output/passive_apis.json
    python passive_discovery.py --config-dir /etc/nginx/conf.d/ --output output/passive_apis.json
"""

import argparse
import json
import logging
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("passive_discovery")


@dataclass
class PassiveAPIInfo:
    """API information discovered passively."""

    url: str
    name: str = ""
    source: str = "passive"
    discovery_method: str = ""
    endpoints: list = field(default_factory=list)
    methods_used: list = field(default_factory=list)
    status_codes: dict = field(default_factory=dict)
    request_volume: int = 0
    volume_category: str = "unknown"
    unique_clients: int = 0
    avg_response_size: float = 0.0
    error_rate: float = 0.0
    time_range: dict = field(default_factory=dict)
    upstream_hosts: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class AccessLogAnalyzer:
    """Analyzes access logs to discover API endpoints and traffic patterns."""

    LOG_PATTERNS = {
        "nginx_combined": re.compile(
            r'(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
            r'"(?P<method>\w+)\s+(?P<path>\S+)\s+HTTP/\S+"\s+'
            r'(?P<status>\d+)\s+(?P<size>\d+)\s+'
            r'"(?P<referer>[^"]*)"\s+"(?P<ua>[^"]*)"'
        ),
        "nginx_json": None,  # Handled separately
        "apache_combined": re.compile(
            r'(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
            r'"(?P<method>\w+)\s+(?P<path>\S+)\s+HTTP/\S+"\s+'
            r'(?P<status>\d+)\s+(?P<size>\d+)'
        ),
    }

    API_PATTERNS = [
        re.compile(r"^/api/"),
        re.compile(r"^/v\d+/"),
        re.compile(r"^/graphql"),
        re.compile(r"\.asmx"),
        re.compile(r"\.svc"),
        re.compile(r"^/rest/"),
        re.compile(r"^/ws/"),
        re.compile(r"^/services/"),
        re.compile(r"^/rpc/"),
    ]

    STATIC_PATTERNS = [
        re.compile(r"\.(js|css|png|jpg|gif|ico|svg|woff|ttf|eot|map)$"),
        re.compile(r"^/static/"),
        re.compile(r"^/assets/"),
        re.compile(r"^/favicon"),
        re.compile(r"^/robots\.txt$"),
        re.compile(r"^/health$"),
        re.compile(r"^/$"),
    ]

    def __init__(self):
        self.logger = logging.getLogger("access_log_analyzer")

    def analyze_directory(self, log_dir: str) -> list[PassiveAPIInfo]:
        """Analyze all log files in a directory."""
        log_path = Path(log_dir)
        if not log_path.exists():
            self.logger.error(f"Log directory not found: {log_dir}")
            return []

        all_entries = []
        log_files = (
            list(log_path.glob("*.log"))
            + list(log_path.glob("*.log.*"))
            + list(log_path.glob("access*"))
        )

        for log_file in log_files:
            if log_file.suffix == ".json":
                entries = self._parse_json_log(str(log_file))
            else:
                entries = self._parse_text_log(str(log_file))
            all_entries.extend(entries)

        self.logger.info(f"Parsed {len(all_entries)} log entries from {len(log_files)} files")
        return self._aggregate_entries(all_entries)

    def _parse_text_log(self, filepath: str) -> list[dict]:
        """Parse a text-format access log."""
        entries = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    for fmt_name, pattern in self.LOG_PATTERNS.items():
                        if pattern is None:
                            continue
                        match = pattern.match(line)
                        if match:
                            entry = match.groupdict()
                            if self._is_api_request(entry.get("path", "")):
                                entries.append(entry)
                            break
        except Exception as e:
            self.logger.error(f"Error parsing log {filepath}: {e}")
        return entries

    def _parse_json_log(self, filepath: str) -> list[dict]:
        """Parse a JSON-lines format access log."""
        entries = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        path = (
                            entry.get("path")
                            or entry.get("uri")
                            or entry.get("request_uri")
                            or ""
                        )
                        if self._is_api_request(path):
                            normalized = {
                                "ip": entry.get("remote_addr", entry.get("client_ip", "")),
                                "method": entry.get("method", entry.get("request_method", "")),
                                "path": path,
                                "status": str(entry.get("status", entry.get("response_code", ""))),
                                "size": str(entry.get("body_bytes_sent", entry.get("bytes", 0))),
                                "time": entry.get("time_local", entry.get("timestamp", "")),
                                "upstream": entry.get("upstream_addr", ""),
                                "host": entry.get("host", entry.get("server_name", "")),
                                "response_time": entry.get(
                                    "request_time", entry.get("response_time", "")
                                ),
                            }
                            entries.append(normalized)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self.logger.error(f"Error parsing JSON log {filepath}: {e}")
        return entries

    def _is_api_request(self, path: str) -> bool:
        """Determine if a request path is an API call (not static content)."""
        if any(p.search(path) for p in self.STATIC_PATTERNS):
            return False
        return any(p.search(path) for p in self.API_PATTERNS)

    def _aggregate_entries(self, entries: list[dict]) -> list[PassiveAPIInfo]:
        """Aggregate log entries into API summaries."""
        api_groups: dict[str, list[dict]] = defaultdict(list)

        for entry in entries:
            base_path = self._normalize_path(entry.get("path", ""))
            if base_path:
                api_groups[base_path].append(entry)

        apis = []
        for base_path, group_entries in api_groups.items():
            methods = Counter(e.get("method", "") for e in group_entries)
            statuses = Counter(e.get("status", "") for e in group_entries)
            ips = set(e.get("ip", "") for e in group_entries if e.get("ip"))
            hosts = set(e.get("host", "") for e in group_entries if e.get("host"))
            upstreams = set(e.get("upstream", "") for e in group_entries if e.get("upstream"))

            total = len(group_entries)
            errors = sum(1 for e in group_entries if e.get("status", "").startswith(("4", "5")))
            sizes = [int(e.get("size", 0)) for e in group_entries if e.get("size", "").isdigit()]

            host = next(iter(hosts), "")
            url = f"https://{host}{base_path}" if host else base_path

            volume = total
            if volume > 100000:
                vol_cat = "very_high"
            elif volume > 10000:
                vol_cat = "high"
            elif volume > 1000:
                vol_cat = "medium"
            else:
                vol_cat = "low"

            # Collect unique endpoint paths under this base
            unique_endpoints = set()
            for e in group_entries:
                path = e.get("path", "")
                if path:
                    unique_endpoints.add(path)

            apis.append(
                PassiveAPIInfo(
                    url=url,
                    name=self._infer_name(base_path),
                    discovery_method="access_log",
                    endpoints=sorted(unique_endpoints)[:50],
                    methods_used=sorted(methods.keys()),
                    status_codes=dict(statuses),
                    request_volume=total,
                    volume_category=vol_cat,
                    unique_clients=len(ips),
                    avg_response_size=sum(sizes) / len(sizes) if sizes else 0,
                    error_rate=errors / total if total > 0 else 0,
                    upstream_hosts=sorted(upstreams),
                )
            )

        apis.sort(key=lambda a: a.request_volume, reverse=True)
        return apis

    def _normalize_path(self, path: str) -> str:
        """Normalize an API path to its base form."""
        parts = path.strip("/").split("/")
        normalized = []
        for part in parts:
            if re.match(r"^\d+$", part):
                normalized.append("{id}")
            elif re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-", part):
                normalized.append("{uuid}")
            elif re.match(r"^[0-9a-f]{24}$", part):
                normalized.append("{objectId}")
            else:
                normalized.append(part)
            if len(normalized) >= 4:
                break
        return "/" + "/".join(normalized) if normalized else ""

    def _infer_name(self, path: str) -> str:
        """Infer an API name from its path."""
        parts = [p for p in path.strip("/").split("/") if not p.startswith("{")]
        name_parts = [p for p in parts if not re.match(r"^v\d+$", p)]
        if name_parts:
            return "-".join(name_parts[:3])
        return "unknown-api"


class ConfigAnalyzer:
    """Analyzes server configuration files to discover upstream APIs."""

    NGINX_UPSTREAM = re.compile(r"upstream\s+(\w+)\s*\{([^}]+)\}", re.MULTILINE | re.DOTALL)
    NGINX_PROXY_PASS = re.compile(r"proxy_pass\s+(https?://\S+);")
    NGINX_LOCATION = re.compile(r"location\s+(\S+)\s*\{")

    def __init__(self):
        self.logger = logging.getLogger("config_analyzer")

    def analyze_nginx_configs(self, config_dir: str) -> list[PassiveAPIInfo]:
        """Analyze nginx configuration files."""
        apis = []
        config_path = Path(config_dir)

        if not config_path.exists():
            self.logger.error(f"Config directory not found: {config_dir}")
            return apis

        for config_file in config_path.rglob("*.conf"):
            try:
                content = config_file.read_text(encoding="utf-8")
                found = self._parse_nginx_config(content, str(config_file))
                apis.extend(found)
            except Exception as e:
                self.logger.error(f"Error parsing config {config_file}: {e}")

        self.logger.info(f"Found {len(apis)} API upstreams in nginx configs")
        return apis

    def _parse_nginx_config(self, content: str, filepath: str) -> list[PassiveAPIInfo]:
        """Parse a single nginx config file."""
        apis = []
        upstreams = {}

        for match in self.NGINX_UPSTREAM.finditer(content):
            name = match.group(1)
            body = match.group(2)
            servers = re.findall(r"server\s+(\S+);", body)
            upstreams[name] = servers

        for match in self.NGINX_PROXY_PASS.finditer(content):
            proxy_url = match.group(1)
            apis.append(
                PassiveAPIInfo(
                    url=proxy_url,
                    source="passive",
                    discovery_method="nginx_config",
                    metadata={"config_file": filepath},
                )
            )

        return apis


class ServiceCatalogClient:
    """Client for querying service catalogs (CMDB, ServiceNow, etc.)."""

    def __init__(self, catalog_url: Optional[str] = None, api_key: Optional[str] = None):
        self.catalog_url = catalog_url
        self.api_key = api_key
        self.logger = logging.getLogger("service_catalog")

    def query_services(self) -> list[PassiveAPIInfo]:
        """Query the service catalog for API services."""
        if not self.catalog_url:
            return []

        apis = []
        try:
            import urllib.request

            headers = {"Accept": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            req = urllib.request.Request(self.catalog_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())

            services = data if isinstance(data, list) else data.get("services", [])
            for svc in services:
                url = svc.get("url") or svc.get("endpoint") or svc.get("base_url") or ""
                if url:
                    apis.append(
                        PassiveAPIInfo(
                            url=url,
                            name=svc.get("name", ""),
                            discovery_method="service_catalog",
                            metadata={
                                "owner": svc.get("owner", ""),
                                "squad": svc.get("squad", svc.get("team", "")),
                                "department": svc.get("department", ""),
                                "environment": svc.get("environment", ""),
                                "criticality": svc.get("criticality", ""),
                            },
                        )
                    )

            self.logger.info(f"Found {len(apis)} APIs in service catalog")
        except Exception as e:
            self.logger.error(f"Error querying service catalog: {e}")

        return apis


def run_passive_discovery(
    log_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
    catalog_url: Optional[str] = None,
) -> list[PassiveAPIInfo]:
    """Run all passive discovery methods."""
    all_apis: list[PassiveAPIInfo] = []

    if log_dir:
        analyzer = AccessLogAnalyzer()
        apis = analyzer.analyze_directory(log_dir)
        all_apis.extend(apis)
        logger.info(f"Log analysis: found {len(apis)} APIs")

    if config_dir:
        config_analyzer = ConfigAnalyzer()
        apis = config_analyzer.analyze_nginx_configs(config_dir)
        all_apis.extend(apis)
        logger.info(f"Config analysis: found {len(apis)} APIs")

    if catalog_url:
        catalog = ServiceCatalogClient(catalog_url)
        apis = catalog.query_services()
        all_apis.extend(apis)
        logger.info(f"Service catalog: found {len(apis)} APIs")

    logger.info(f"Total passive discovery: {len(all_apis)} APIs")
    return all_apis


def main():
    parser = argparse.ArgumentParser(description="Passive API Discovery")
    parser.add_argument("--log-dir", help="Directory with access logs")
    parser.add_argument("--config-dir", help="Directory with server configs (nginx, etc)")
    parser.add_argument("--catalog-url", help="Service catalog API URL")
    parser.add_argument("--output", default="output/passive_apis.json", help="Output file")

    args = parser.parse_args()

    if not any([args.log_dir, args.config_dir, args.catalog_url]):
        print("Error: At least one source required (--log-dir, --config-dir, --catalog-url)")
        return

    apis = run_passive_discovery(
        log_dir=args.log_dir,
        config_dir=args.config_dir,
        catalog_url=args.catalog_url,
    )

    output = {
        "passive_discovery_metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_discovered": len(apis),
            "methods_used": list(set(a.discovery_method for a in apis)),
        },
        "apis": [asdict(a) for a in apis],
    }

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nPassive discovery complete: {len(apis)} APIs found")
    for api in apis[:10]:
        print(f"  - {api.name or api.url} ({api.discovery_method}, vol={api.request_volume})")
    if len(apis) > 10:
        print(f"  ... and {len(apis) - 10} more")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()

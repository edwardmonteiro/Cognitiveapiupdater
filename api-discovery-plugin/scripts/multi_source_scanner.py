#!/usr/bin/env python3
"""
Multi-Source API Scanner

Discovers APIs from multiple sources:
- Catalog: CSV/JSON files, API Gateways (Kong, Apigee), Service Mesh
- Git: GitHub/GitLab repositories (OpenAPI specs, project files)
- Logs: Access logs (nginx, Apache, API Gateway)
- Network: Active port scanning and service detection

Usage:
    python multi_source_scanner.py --sources catalog,git,logs \
        --input apis.csv \
        --git-org my-org \
        --log-dir /var/log/nginx/ \
        --output raw_apis.json
"""

import argparse
import csv
import glob
import json
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("multi_source_scanner")


@dataclass
class DiscoveredAPI:
    """Represents a discovered API before classification."""

    url: str
    name: str = ""
    source: str = ""
    source_detail: str = ""
    discovered_at: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.discovered_at:
            self.discovered_at = datetime.now(timezone.utc).isoformat()
        if not self.name:
            self.name = self._infer_name()

    def _infer_name(self) -> str:
        """Infer API name from URL."""
        parsed = urlparse(self.url)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if path_parts:
            name_parts = []
            for part in path_parts[:3]:
                if not re.match(r"^v\d+", part):
                    name_parts.append(part)
            if name_parts:
                return "-".join(name_parts)
        return parsed.hostname or "unknown-api"


class CatalogScanner:
    """Scans API catalogs: CSV, JSON, API Gateways."""

    def __init__(self):
        self.logger = logging.getLogger("catalog_scanner")

    def scan_csv(self, filepath: str) -> list[DiscoveredAPI]:
        """Parse a CSV file containing API information."""
        apis = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    url = row.get("url") or row.get("URL") or row.get("endpoint") or ""
                    name = row.get("name") or row.get("Name") or row.get("api_name") or ""
                    if url:
                        api = DiscoveredAPI(
                            url=url.strip(),
                            name=name.strip() if name else "",
                            source="catalog",
                            source_detail=f"csv:{filepath}",
                            metadata={
                                k: v for k, v in row.items() if k not in ("url", "URL", "endpoint")
                            },
                        )
                        apis.append(api)
            self.logger.info(f"Found {len(apis)} APIs in CSV: {filepath}")
        except FileNotFoundError:
            self.logger.error(f"CSV file not found: {filepath}")
        except Exception as e:
            self.logger.error(f"Error parsing CSV {filepath}: {e}")
        return apis

    def scan_json(self, filepath: str) -> list[DiscoveredAPI]:
        """Parse a JSON file containing API information."""
        apis = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            items = data if isinstance(data, list) else data.get("apis", data.get("services", []))
            for item in items:
                if isinstance(item, str):
                    apis.append(
                        DiscoveredAPI(url=item, source="catalog", source_detail=f"json:{filepath}")
                    )
                elif isinstance(item, dict):
                    url = item.get("url") or item.get("endpoint") or item.get("base_url") or ""
                    if url:
                        apis.append(
                            DiscoveredAPI(
                                url=url,
                                name=item.get("name", ""),
                                source="catalog",
                                source_detail=f"json:{filepath}",
                                metadata={
                                    k: v
                                    for k, v in item.items()
                                    if k not in ("url", "endpoint", "base_url")
                                },
                            )
                        )
            self.logger.info(f"Found {len(apis)} APIs in JSON: {filepath}")
        except FileNotFoundError:
            self.logger.error(f"JSON file not found: {filepath}")
        except Exception as e:
            self.logger.error(f"Error parsing JSON {filepath}: {e}")
        return apis

    def scan_kong_gateway(self, gateway_url: str, api_key: Optional[str] = None) -> list[DiscoveredAPI]:
        """Discover APIs from Kong API Gateway admin API."""
        apis = []
        try:
            import urllib.request

            headers = {}
            if api_key:
                headers["apikey"] = api_key

            services_url = f"{gateway_url.rstrip('/')}/services"
            req = urllib.request.Request(services_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())

            for svc in data.get("data", []):
                url = f"{svc.get('protocol', 'https')}://{svc.get('host', '')}:{svc.get('port', 443)}{svc.get('path', '/')}"
                apis.append(
                    DiscoveredAPI(
                        url=url,
                        name=svc.get("name", ""),
                        source="catalog",
                        source_detail=f"kong:{gateway_url}",
                        metadata={
                            "kong_id": svc.get("id", ""),
                            "enabled": svc.get("enabled", True),
                            "retries": svc.get("retries", 5),
                            "tags": svc.get("tags", []),
                        },
                    )
                )
            self.logger.info(f"Found {len(apis)} APIs in Kong: {gateway_url}")
        except Exception as e:
            self.logger.error(f"Error connecting to Kong {gateway_url}: {e}")
        return apis

    def scan_apigee(self, org_url: str, token: Optional[str] = None) -> list[DiscoveredAPI]:
        """Discover APIs from Apigee API Gateway."""
        apis = []
        try:
            import urllib.request

            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            proxies_url = f"{org_url.rstrip('/')}/apis"
            req = urllib.request.Request(proxies_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())

            for proxy_name in data:
                apis.append(
                    DiscoveredAPI(
                        url=f"{org_url.rstrip('/')}/apis/{proxy_name}",
                        name=proxy_name,
                        source="catalog",
                        source_detail=f"apigee:{org_url}",
                    )
                )
            self.logger.info(f"Found {len(apis)} APIs in Apigee: {org_url}")
        except Exception as e:
            self.logger.error(f"Error connecting to Apigee {org_url}: {e}")
        return apis

    def scan_file(self, filepath: str) -> list[DiscoveredAPI]:
        """Auto-detect file type and scan."""
        if filepath.endswith(".csv"):
            return self.scan_csv(filepath)
        elif filepath.endswith(".json"):
            return self.scan_json(filepath)
        else:
            self.logger.warning(f"Unsupported file type: {filepath}. Trying JSON...")
            return self.scan_json(filepath)


class GitScanner:
    """Scans Git repositories for API projects."""

    API_FILE_PATTERNS = [
        "openapi.yaml",
        "openapi.yml",
        "openapi.json",
        "swagger.yaml",
        "swagger.yml",
        "swagger.json",
        "api.yaml",
        "api.yml",
    ]

    PROJECT_INDICATORS = {
        "package.json": "nodejs",
        "pom.xml": "java",
        "build.gradle": "java",
        "requirements.txt": "python",
        "setup.py": "python",
        "pyproject.toml": "python",
        "go.mod": "go",
        "Gemfile": "ruby",
        "Cargo.toml": "rust",
        "*.csproj": "dotnet",
    }

    def __init__(self):
        self.logger = logging.getLogger("git_scanner")

    def scan_local_repos(self, base_dir: str) -> list[DiscoveredAPI]:
        """Scan local Git repositories for API projects."""
        apis = []
        base_path = Path(base_dir)

        if not base_path.exists():
            self.logger.error(f"Directory not found: {base_dir}")
            return apis

        for repo_dir in base_path.iterdir():
            if not repo_dir.is_dir():
                continue
            if (repo_dir / ".git").exists():
                found = self._scan_single_repo(str(repo_dir))
                apis.extend(found)

        self.logger.info(f"Found {len(apis)} APIs in local repos under {base_dir}")
        return apis

    def _scan_single_repo(self, repo_path: str) -> list[DiscoveredAPI]:
        """Scan a single repository for API indicators."""
        apis = []
        repo = Path(repo_path)
        repo_name = repo.name

        for pattern in self.API_FILE_PATTERNS:
            matches = list(repo.rglob(pattern))
            for match in matches:
                api_info = self._parse_api_spec(str(match))
                if api_info:
                    apis.append(
                        DiscoveredAPI(
                            url=api_info.get("url", f"repo://{repo_name}"),
                            name=api_info.get("title", repo_name),
                            source="git",
                            source_detail=f"repo:{repo_path}",
                            metadata={
                                "spec_file": str(match.relative_to(repo)),
                                "spec_version": api_info.get("version", ""),
                                "language": self._detect_language(repo_path),
                                "repo": repo_name,
                            },
                        )
                    )

        if not apis:
            lang = self._detect_language(repo_path)
            if lang and self._looks_like_api_project(repo_path):
                apis.append(
                    DiscoveredAPI(
                        url=f"repo://{repo_name}",
                        name=repo_name,
                        source="git",
                        source_detail=f"repo:{repo_path}",
                        metadata={"language": lang, "repo": repo_name, "has_spec": False},
                    )
                )

        return apis

    def _parse_api_spec(self, filepath: str) -> Optional[dict]:
        """Parse an OpenAPI/Swagger spec to extract basic info."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                if filepath.endswith(".json"):
                    spec = json.load(f)
                else:
                    try:
                        import yaml

                        spec = yaml.safe_load(f)
                    except ImportError:
                        return None

            info = spec.get("info", {})
            servers = spec.get("servers", [])
            url = servers[0].get("url", "") if servers else ""

            # Swagger 2.0 uses host/basePath
            if not url and "host" in spec:
                scheme = (spec.get("schemes") or ["https"])[0]
                url = f"{scheme}://{spec['host']}{spec.get('basePath', '/')}"

            return {
                "title": info.get("title", ""),
                "version": info.get("version", ""),
                "description": info.get("description", ""),
                "url": url,
                "contact": info.get("contact", {}),
            }
        except Exception as e:
            self.logger.debug(f"Error parsing spec {filepath}: {e}")
            return None

    def _detect_language(self, repo_path: str) -> str:
        """Detect primary language of a repository."""
        repo = Path(repo_path)
        for indicator_file, lang in self.PROJECT_INDICATORS.items():
            if "*" in indicator_file:
                if list(repo.rglob(indicator_file)):
                    return lang
            elif (repo / indicator_file).exists():
                return lang
        return ""

    def _looks_like_api_project(self, repo_path: str) -> bool:
        """Check if repo likely contains an API (routes, controllers, etc.)."""
        api_indicators = [
            "routes", "controllers", "handlers", "endpoints",
            "api", "views", "resources", "server",
        ]
        repo = Path(repo_path)
        for indicator in api_indicators:
            if list(repo.rglob(f"*{indicator}*")):
                return True
        return False

    def scan_github_org(self, org: str, token: Optional[str] = None) -> list[DiscoveredAPI]:
        """Scan GitHub organization for API repositories."""
        apis = []
        try:
            import urllib.request

            headers = {"Accept": "application/vnd.github.v3+json"}
            if token:
                headers["Authorization"] = f"token {token}"

            page = 1
            while True:
                url = f"https://api.github.com/orgs/{org}/repos?per_page=100&page={page}"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as response:
                    repos = json.loads(response.read().decode())

                if not repos:
                    break

                for repo in repos:
                    if repo.get("archived"):
                        continue
                    spec_urls = self._check_github_repo_for_specs(
                        org, repo["name"], headers
                    )
                    for spec_url in spec_urls:
                        apis.append(
                            DiscoveredAPI(
                                url=spec_url.get("server_url", f"github://{org}/{repo['name']}"),
                                name=repo["name"],
                                source="git",
                                source_detail=f"github:{org}/{repo['name']}",
                                metadata={
                                    "repo_url": repo["html_url"],
                                    "language": repo.get("language", ""),
                                    "default_branch": repo.get("default_branch", "main"),
                                    "spec_path": spec_url.get("path", ""),
                                },
                            )
                        )

                    if not spec_urls and self._github_repo_looks_like_api(repo):
                        apis.append(
                            DiscoveredAPI(
                                url=f"github://{org}/{repo['name']}",
                                name=repo["name"],
                                source="git",
                                source_detail=f"github:{org}/{repo['name']}",
                                metadata={
                                    "repo_url": repo["html_url"],
                                    "language": repo.get("language", ""),
                                    "has_spec": False,
                                },
                            )
                        )
                page += 1

            self.logger.info(f"Found {len(apis)} APIs in GitHub org: {org}")
        except Exception as e:
            self.logger.error(f"Error scanning GitHub org {org}: {e}")
        return apis

    def _check_github_repo_for_specs(
        self, org: str, repo: str, headers: dict
    ) -> list[dict]:
        """Check if a GitHub repo contains API spec files."""
        results = []
        for pattern in self.API_FILE_PATTERNS:
            try:
                import urllib.request

                url = f"https://api.github.com/search/code?q=filename:{pattern}+repo:{org}/{repo}"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                if data.get("total_count", 0) > 0:
                    results.append({"path": pattern, "server_url": ""})
            except Exception:
                pass
        return results

    def _github_repo_looks_like_api(self, repo: dict) -> bool:
        """Heuristic: does repo name/description suggest it's an API?"""
        api_keywords = ["api", "service", "gateway", "server", "backend", "rest", "graphql"]
        name = (repo.get("name") or "").lower()
        desc = (repo.get("description") or "").lower()
        topics = [t.lower() for t in (repo.get("topics") or [])]
        text = f"{name} {desc} {' '.join(topics)}"
        return any(kw in text for kw in api_keywords)


class LogScanner:
    """Scans access logs to discover API endpoints."""

    NGINX_PATTERN = re.compile(
        r'(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
        r'"(?P<method>\w+)\s+(?P<path>\S+)\s+HTTP/\S+"\s+'
        r'(?P<status>\d+)\s+(?P<size>\d+)'
    )

    APACHE_PATTERN = re.compile(
        r'(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+'
        r'"(?P<method>\w+)\s+(?P<path>\S+)\s+HTTP/\S+"\s+'
        r'(?P<status>\d+)\s+(?P<size>\d+)'
    )

    API_PATH_PATTERNS = [
        re.compile(r"/api/"),
        re.compile(r"/v\d+/"),
        re.compile(r"/graphql"),
        re.compile(r"\.asmx"),
        re.compile(r"\.svc"),
        re.compile(r"/rest/"),
        re.compile(r"/ws/"),
        re.compile(r"/services/"),
    ]

    def __init__(self):
        self.logger = logging.getLogger("log_scanner")

    def scan_log_directory(self, log_dir: str) -> list[DiscoveredAPI]:
        """Scan all log files in a directory."""
        apis = []
        endpoint_counts: dict[str, int] = {}
        log_path = Path(log_dir)

        if not log_path.exists():
            self.logger.error(f"Log directory not found: {log_dir}")
            return apis

        log_files = list(log_path.glob("*.log")) + list(log_path.glob("*.log.*"))

        for log_file in log_files:
            self._parse_log_file(str(log_file), endpoint_counts)

        for base_path, count in endpoint_counts.items():
            apis.append(
                DiscoveredAPI(
                    url=base_path,
                    source="logs",
                    source_detail=f"logdir:{log_dir}",
                    metadata={"request_count": count, "estimated_volume": self._volume_category(count)},
                )
            )

        self.logger.info(f"Found {len(apis)} unique API base paths in logs at {log_dir}")
        return apis

    def _parse_log_file(self, filepath: str, endpoint_counts: dict[str, int]):
        """Parse a single log file and extract API endpoints."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    match = self.NGINX_PATTERN.match(line) or self.APACHE_PATTERN.match(line)
                    if not match:
                        continue
                    path = match.group("path")
                    if self._is_api_path(path):
                        base_path = self._extract_base_path(path)
                        if base_path:
                            endpoint_counts[base_path] = endpoint_counts.get(base_path, 0) + 1
        except Exception as e:
            self.logger.error(f"Error parsing log file {filepath}: {e}")

    def _is_api_path(self, path: str) -> bool:
        """Check if a path looks like an API endpoint."""
        return any(pattern.search(path) for pattern in self.API_PATH_PATTERNS)

    def _extract_base_path(self, path: str) -> str:
        """Extract the base API path (e.g., /api/v1/payments from /api/v1/payments/123)."""
        parts = path.strip("/").split("/")
        base_parts = []
        for part in parts:
            if re.match(r"^\d+$", part):
                break
            if re.match(r"^[0-9a-f]{8}-", part):
                break
            base_parts.append(part)
            if len(base_parts) >= 4:
                break
        return "/" + "/".join(base_parts) if base_parts else ""

    def scan_json_logs(self, log_dir: str) -> list[DiscoveredAPI]:
        """Parse JSON-formatted access logs (e.g., from API Gateways)."""
        apis = []
        endpoint_counts: dict[str, dict] = {}
        log_path = Path(log_dir)

        for log_file in log_path.glob("*.json"):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            path = entry.get("path") or entry.get("uri") or entry.get("request_uri", "")
                            host = entry.get("host") or entry.get("upstream_host", "")
                            if path and self._is_api_path(path):
                                base = self._extract_base_path(path)
                                key = f"{host}{base}" if host else base
                                if key not in endpoint_counts:
                                    endpoint_counts[key] = {"count": 0, "host": host, "path": base}
                                endpoint_counts[key]["count"] += 1
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                self.logger.error(f"Error reading JSON log {log_file}: {e}")

        for key, info in endpoint_counts.items():
            url = f"https://{info['host']}{info['path']}" if info["host"] else info["path"]
            apis.append(
                DiscoveredAPI(
                    url=url,
                    source="logs",
                    source_detail=f"jsonlog:{log_dir}",
                    metadata={
                        "request_count": info["count"],
                        "estimated_volume": self._volume_category(info["count"]),
                    },
                )
            )

        self.logger.info(f"Found {len(apis)} APIs in JSON logs at {log_dir}")
        return apis

    def _volume_category(self, count: int) -> str:
        """Categorize request volume."""
        if count > 100000:
            return "very_high"
        elif count > 10000:
            return "high"
        elif count > 1000:
            return "medium"
        return "low"


class MultiSourceScanner:
    """Orchestrates scanning across all sources."""

    def __init__(self, workers: int = 20):
        self.workers = workers
        self.catalog_scanner = CatalogScanner()
        self.git_scanner = GitScanner()
        self.log_scanner = LogScanner()
        self.logger = logging.getLogger("multi_source_scanner")

    def scan(
        self,
        sources: list[str],
        input_file: Optional[str] = None,
        catalog_url: Optional[str] = None,
        git_org: Optional[str] = None,
        git_dir: Optional[str] = None,
        log_dir: Optional[str] = None,
        network_range: Optional[str] = None,
        ports: Optional[str] = None,
    ) -> list[DiscoveredAPI]:
        """Execute multi-source scanning."""
        all_apis: list[DiscoveredAPI] = []
        tasks = []

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            if "catalog" in sources:
                if input_file:
                    tasks.append(
                        executor.submit(self.catalog_scanner.scan_file, input_file)
                    )
                if catalog_url:
                    tasks.append(
                        executor.submit(
                            self.catalog_scanner.scan_kong_gateway, catalog_url
                        )
                    )

            if "git" in sources:
                if git_org:
                    token = os.environ.get("GITHUB_TOKEN")
                    tasks.append(
                        executor.submit(
                            self.git_scanner.scan_github_org, git_org, token
                        )
                    )
                if git_dir:
                    tasks.append(
                        executor.submit(self.git_scanner.scan_local_repos, git_dir)
                    )

            if "logs" in sources and log_dir:
                tasks.append(
                    executor.submit(self.log_scanner.scan_log_directory, log_dir)
                )
                tasks.append(
                    executor.submit(self.log_scanner.scan_json_logs, log_dir)
                )

            if "network" in sources and network_range:
                self.logger.info(
                    "Network scanning delegated to active_probe.py"
                )

            for future in as_completed(tasks):
                try:
                    result = future.result()
                    all_apis.extend(result)
                except Exception as e:
                    self.logger.error(f"Source scan failed: {e}")

        deduplicated = self._deduplicate(all_apis)
        self.logger.info(
            f"Total discovered: {len(all_apis)}, After dedup: {len(deduplicated)}"
        )
        return deduplicated

    def _deduplicate(self, apis: list[DiscoveredAPI]) -> list[DiscoveredAPI]:
        """Remove duplicate APIs discovered from multiple sources."""
        seen: dict[str, DiscoveredAPI] = {}
        for api in apis:
            normalized = self._normalize_url(api.url)
            if normalized in seen:
                existing = seen[normalized]
                existing.metadata["additional_sources"] = existing.metadata.get(
                    "additional_sources", []
                )
                existing.metadata["additional_sources"].append(api.source)
            else:
                seen[normalized] = api
        return list(seen.values())

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        url = url.rstrip("/").lower()
        url = re.sub(r":\d+", "", url)
        return url


def save_results(apis: list[DiscoveredAPI], output_path: str):
    """Save discovered APIs to JSON file."""
    output = {
        "scan_metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_discovered": len(apis),
        },
        "apis": [asdict(api) for api in apis],
    }
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    logger.info(f"Results saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Multi-Source API Scanner")
    parser.add_argument(
        "--sources",
        default="catalog",
        help="Comma-separated sources: catalog,git,logs,network",
    )
    parser.add_argument("--input", help="Input CSV/JSON file path")
    parser.add_argument("--catalog-url", help="API Gateway catalog URL")
    parser.add_argument("--git-org", help="GitHub/GitLab organization")
    parser.add_argument("--git-dir", help="Local Git repositories directory")
    parser.add_argument("--log-dir", help="Access logs directory")
    parser.add_argument("--network-range", help="CIDR range for network scan")
    parser.add_argument("--ports", default="80,443,8080,3000,50051", help="Ports to scan")
    parser.add_argument("--output", default="output/raw_apis.json", help="Output file")
    parser.add_argument("--workers", type=int, default=20, help="Parallel workers")

    args = parser.parse_args()
    sources = [s.strip() for s in args.sources.split(",")]

    scanner = MultiSourceScanner(workers=args.workers)
    apis = scanner.scan(
        sources=sources,
        input_file=args.input,
        catalog_url=args.catalog_url,
        git_org=args.git_org,
        git_dir=args.git_dir,
        log_dir=args.log_dir,
        network_range=args.network_range,
        ports=args.ports,
    )

    save_results(apis, args.output)
    print(f"\nDiscovery complete: {len(apis)} APIs found")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()

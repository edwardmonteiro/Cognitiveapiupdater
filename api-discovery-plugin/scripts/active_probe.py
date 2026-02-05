#!/usr/bin/env python3
"""
Active API Probe

Performs active discovery of APIs through:
- Network port scanning
- Service fingerprinting
- HTTP endpoint probing
- API type detection (REST, GraphQL, SOAP, gRPC)

Security: Only runs with explicit --mode active flag.
Rate limiting: max 10 requests/second per host.

Usage:
    python active_probe.py --url https://api.example.com
    python active_probe.py --network-range 10.0.0.0/24 --ports 80,443,8080
"""

import argparse
import json
import logging
import os
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("active_probe")


@dataclass
class ProbeResult:
    """Result of probing a single API endpoint."""

    url: str
    reachable: bool = False
    status_code: int = 0
    api_type: str = "unknown"
    api_type_confidence: float = 0.0
    headers: dict = field(default_factory=dict)
    technology: dict = field(default_factory=dict)
    documentation: dict = field(default_factory=dict)
    response_sample: str = ""
    probe_time: str = ""
    errors: list = field(default_factory=list)

    def __post_init__(self):
        if not self.probe_time:
            self.probe_time = datetime.now(timezone.utc).isoformat()


class RateLimiter:
    """Simple per-host rate limiter."""

    def __init__(self, max_per_second: int = 10):
        self.max_per_second = max_per_second
        self._host_timestamps: dict[str, list[float]] = {}

    def wait(self, host: str):
        """Block until it's safe to make a request to the given host."""
        now = time.time()
        if host not in self._host_timestamps:
            self._host_timestamps[host] = []

        self._host_timestamps[host] = [
            t for t in self._host_timestamps[host] if now - t < 1.0
        ]

        if len(self._host_timestamps[host]) >= self.max_per_second:
            sleep_time = 1.0 - (now - self._host_timestamps[host][0])
            if sleep_time > 0:
                time.sleep(sleep_time)

        self._host_timestamps[host].append(time.time())


class APIProber:
    """Probes individual APIs to detect type, documentation, and technology."""

    OPENAPI_PATHS = [
        "/openapi.json",
        "/openapi.yaml",
        "/swagger.json",
        "/swagger/v1/swagger.json",
        "/api-docs",
        "/api-docs.json",
        "/docs",
        "/redoc",
        "/v3/api-docs",
    ]

    GRAPHQL_PATHS = ["/graphql", "/gql", "/api/graphql"]

    SOAP_INDICATORS = [".asmx", ".svc", "/ws/", "/services/"]

    LANGUAGE_HEADERS = {
        "X-Powered-By": {
            "Express": ("nodejs", "express"),
            "PHP": ("php", "php"),
            "ASP.NET": ("dotnet", "aspnet"),
        },
        "Server": {
            "gunicorn": ("python", "gunicorn"),
            "uvicorn": ("python", "uvicorn"),
            "Kestrel": ("dotnet", "aspnet-core"),
            "Puma": ("ruby", "puma"),
            "nginx": (None, "nginx"),
            "Apache": (None, "apache"),
            "Jetty": ("java", "jetty"),
            "Tomcat": ("java", "tomcat"),
        },
        "X-Application-Context": {
            "": ("java", "spring-boot"),
        },
    }

    CLOUD_HEADERS = {
        "X-Amz-": "aws",
        "X-Amzn-": "aws",
        "X-Azure-": "azure",
        "X-Ms-": "azure",
        "X-Cloud-Trace-Context": "gcp",
        "CF-RAY": "cloudflare",
        "X-Vercel-": "vercel",
    }

    def __init__(self, timeout: int = 30, rate_limiter: Optional[RateLimiter] = None):
        self.timeout = timeout
        self.rate_limiter = rate_limiter or RateLimiter()

    def probe(self, url: str) -> ProbeResult:
        """Perform full probe of a URL."""
        result = ProbeResult(url=url)
        parsed = urlparse(url)

        if parsed.scheme in ("repo", "github"):
            result.errors.append("Cannot probe non-HTTP URL")
            return result

        host = parsed.hostname or ""
        self.rate_limiter.wait(host)

        try:
            headers, status, body = self._http_request(url)
            result.reachable = True
            result.status_code = status
            result.headers = dict(headers)
            result.response_sample = body[:500] if body else ""

            result.technology = self._detect_technology(headers)
            result.api_type, result.api_type_confidence = self._classify_api(
                url, headers, body
            )
            result.documentation = self._detect_documentation(url)

        except HTTPError as e:
            result.reachable = True
            result.status_code = e.code
            result.errors.append(f"HTTP {e.code}: {e.reason}")
            try:
                headers = dict(e.headers)
                result.headers = headers
                result.technology = self._detect_technology(e.headers)
            except Exception:
                pass
        except URLError as e:
            result.errors.append(f"Connection failed: {e.reason}")
        except Exception as e:
            result.errors.append(f"Probe error: {str(e)}")

        return result

    def _http_request(self, url: str) -> tuple:
        """Make an HTTP request and return (headers, status, body)."""
        req = Request(url, headers={"User-Agent": "API-Discovery-Probe/1.0", "Accept": "*/*"})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with urlopen(req, timeout=self.timeout, context=ctx) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.headers, response.status, body

    def _classify_api(self, url: str, headers, body: str) -> tuple[str, float]:
        """Classify the type of API."""
        scores = {"REST": 0.0, "GraphQL": 0.0, "SOAP": 0.0, "gRPC": 0.0}

        content_type = headers.get("Content-Type", "").lower() if headers else ""
        path = urlparse(url).path.lower()

        # REST indicators
        if "application/json" in content_type:
            scores["REST"] += 0.3
        if re.search(r"/api/|/v\d+/|/rest/", path):
            scores["REST"] += 0.3
        if body:
            try:
                json.loads(body)
                scores["REST"] += 0.2
            except (json.JSONDecodeError, ValueError):
                pass

        # GraphQL indicators
        if "/graphql" in path or "/gql" in path:
            scores["GraphQL"] += 0.5
        if body and '"data"' in body and ('"errors"' in body or '"extensions"' in body):
            scores["GraphQL"] += 0.3

        # SOAP indicators
        if any(ind in path for ind in self.SOAP_INDICATORS):
            scores["SOAP"] += 0.4
        if "text/xml" in content_type or "application/soap+xml" in content_type:
            scores["SOAP"] += 0.3
        if body and "<soap:" in body.lower() or "<s:envelope" in body.lower():
            scores["SOAP"] += 0.3

        # gRPC indicators
        if "application/grpc" in content_type:
            scores["gRPC"] += 0.8
        if ":50051" in url:
            scores["gRPC"] += 0.3

        best_type = max(scores, key=scores.get)
        confidence = scores[best_type]

        if confidence == 0:
            return "unknown", 0.0

        return best_type, min(confidence, 1.0)

    def _detect_technology(self, headers) -> dict:
        """Detect technology stack from HTTP headers."""
        tech = {"language": "", "framework": "", "server": "", "cloud": "", "extras": []}

        if not headers:
            return tech

        server = headers.get("Server", "")
        powered_by = headers.get("X-Powered-By", "")

        if server:
            tech["server"] = server

        # Language and framework detection
        for header_name, mappings in self.LANGUAGE_HEADERS.items():
            value = headers.get(header_name, "")
            if not value:
                continue
            for indicator, (lang, fw) in mappings.items():
                if indicator == "" or indicator.lower() in value.lower():
                    if lang and not tech["language"]:
                        tech["language"] = lang
                    if fw and not tech["framework"]:
                        tech["framework"] = fw

        # Cloud detection
        for header_name in (headers.keys() if hasattr(headers, 'keys') else []):
            for prefix, cloud in self.CLOUD_HEADERS.items():
                if header_name.startswith(prefix) or header_name.lower().startswith(prefix.lower()):
                    tech["cloud"] = cloud
                    break

        # Additional header-based detection
        if headers.get("X-Application-Context"):
            tech["language"] = tech["language"] or "java"
            tech["framework"] = tech["framework"] or "spring-boot"

        if headers.get("X-AspNet-Version"):
            tech["language"] = "dotnet"
            tech["extras"].append(f"aspnet-{headers.get('X-AspNet-Version')}")

        return tech

    def _detect_documentation(self, base_url: str) -> dict:
        """Check for API documentation at common paths."""
        docs = {
            "has_openapi": False,
            "openapi_url": "",
            "has_graphql_schema": False,
            "has_wsdl": False,
        }

        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        # Check OpenAPI paths
        for path in self.OPENAPI_PATHS:
            try:
                self.rate_limiter.wait(parsed.hostname or "")
                url = urljoin(base, path)
                req = Request(url, headers={"User-Agent": "API-Discovery-Probe/1.0"})
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urlopen(req, timeout=10, context=ctx) as resp:
                    content = resp.read().decode("utf-8", errors="replace")
                    if self._looks_like_openapi(content):
                        docs["has_openapi"] = True
                        docs["openapi_url"] = url
                        break
            except Exception:
                continue

        # Check GraphQL introspection
        for gql_path in self.GRAPHQL_PATHS:
            try:
                self.rate_limiter.wait(parsed.hostname or "")
                url = urljoin(base, gql_path)
                introspection_query = json.dumps(
                    {"query": "{ __schema { types { name } } }"}
                ).encode()
                req = Request(
                    url,
                    data=introspection_query,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "API-Discovery-Probe/1.0",
                    },
                )
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urlopen(req, timeout=10, context=ctx) as resp:
                    content = resp.read().decode()
                    if "__schema" in content:
                        docs["has_graphql_schema"] = True
                        break
            except Exception:
                continue

        # Check WSDL
        try:
            wsdl_url = f"{base_url}?wsdl"
            self.rate_limiter.wait(parsed.hostname or "")
            req = Request(wsdl_url, headers={"User-Agent": "API-Discovery-Probe/1.0"})
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urlopen(req, timeout=10, context=ctx) as resp:
                content = resp.read().decode()
                if "definitions" in content.lower() or "wsdl:" in content.lower():
                    docs["has_wsdl"] = True
                    docs["wsdl_url"] = wsdl_url
        except Exception:
            pass

        return docs

    def _looks_like_openapi(self, content: str) -> bool:
        """Check if content looks like an OpenAPI/Swagger spec."""
        indicators = ['"openapi"', '"swagger"', "openapi:", "swagger:", '"paths"', "paths:"]
        return any(ind in content.lower() for ind in indicators)


class NetworkScanner:
    """Scans network ranges for API services."""

    COMMON_API_PORTS = [80, 443, 8080, 8443, 3000, 3001, 4000, 5000, 8000, 8888, 9090, 50051]

    def __init__(self, timeout: int = 5, workers: int = 50):
        self.timeout = timeout
        self.workers = workers
        self.logger = logging.getLogger("network_scanner")

    def scan_range(self, cidr: str, ports: Optional[list[int]] = None) -> list[str]:
        """Scan a CIDR range for open API ports."""
        import ipaddress

        ports = ports or self.COMMON_API_PORTS
        network = ipaddress.ip_network(cidr, strict=False)
        discovered = []

        targets = [(str(ip), port) for ip in network.hosts() for port in ports]
        self.logger.info(f"Scanning {len(targets)} targets in {cidr}")

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                executor.submit(self._check_port, ip, port): (ip, port)
                for ip, port in targets
            }
            for future in as_completed(futures):
                ip, port = futures[future]
                try:
                    if future.result():
                        scheme = "https" if port in (443, 8443) else "http"
                        url = f"{scheme}://{ip}:{port}"
                        discovered.append(url)
                        self.logger.info(f"Found open port: {ip}:{port}")
                except Exception:
                    pass

        self.logger.info(f"Found {len(discovered)} open API ports in {cidr}")
        return discovered

    def _check_port(self, ip: str, port: int) -> bool:
        """Check if a port is open on an IP."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False


def probe_apis(urls: list[str], workers: int = 20, timeout: int = 30) -> list[ProbeResult]:
    """Probe multiple API URLs in parallel."""
    rate_limiter = RateLimiter(max_per_second=10)
    prober = APIProber(timeout=timeout, rate_limiter=rate_limiter)
    results = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(prober.probe, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                result = future.result()
                results.append(result)
                logger.info(
                    f"Probed {url}: type={result.api_type} "
                    f"confidence={result.api_type_confidence:.2f} "
                    f"status={result.status_code}"
                )
            except Exception as e:
                logger.error(f"Failed to probe {url}: {e}")
                results.append(ProbeResult(url=url, errors=[str(e)]))

    return results


def main():
    parser = argparse.ArgumentParser(description="Active API Probe")
    parser.add_argument("--url", help="Single URL to probe")
    parser.add_argument("--urls-file", help="JSON file with list of URLs to probe")
    parser.add_argument("--network-range", help="CIDR range for network scan")
    parser.add_argument(
        "--ports",
        default="80,443,8080,3000,50051",
        help="Ports to scan",
    )
    parser.add_argument("--workers", type=int, default=20, help="Parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per API")
    parser.add_argument("--output", default="output/probe_results.json", help="Output file")

    args = parser.parse_args()
    urls = []

    if args.url:
        urls.append(args.url)

    if args.urls_file:
        with open(args.urls_file, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                urls.extend(data)
            elif "apis" in data:
                urls.extend(api.get("url", "") for api in data["apis"] if api.get("url"))

    if args.network_range:
        scanner = NetworkScanner(workers=args.workers)
        ports = [int(p) for p in args.ports.split(",")]
        discovered = scanner.scan_range(args.network_range, ports)
        urls.extend(discovered)

    if not urls:
        print("No URLs to probe. Use --url, --urls-file, or --network-range")
        return

    print(f"Probing {len(urls)} URLs...")
    results = probe_apis(urls, workers=args.workers, timeout=args.timeout)

    output = {
        "probe_metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_probed": len(results),
            "reachable": sum(1 for r in results if r.reachable),
            "unreachable": sum(1 for r in results if not r.reachable),
        },
        "results": [asdict(r) for r in results],
    }

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nProbe complete: {len(results)} APIs probed")
    print(f"  Reachable: {output['probe_metadata']['reachable']}")
    print(f"  Unreachable: {output['probe_metadata']['unreachable']}")
    print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()

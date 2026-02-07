# OWASP Top 10 Security Review

**Project:** API Discovery & Classification Plugin
**Date:** 2026-02-07
**Scope:** All Python scripts (`scripts/`), plugin configuration, and documentation
**Methodology:** Manual code review against OWASP Top 10:2021

---

## Summary

| # | Category | Severity | Findings |
|---|----------|----------|----------|
| A01 | Broken Access Control | Medium | 3 |
| A02 | Cryptographic Failures | **Critical** | 3 |
| A03 | Injection | High | 4 |
| A04 | Insecure Design | Medium | 3 |
| A05 | Security Misconfiguration | High | 4 |
| A06 | Vulnerable and Outdated Components | Low | 2 |
| A07 | Identification and Authentication Failures | High | 3 |
| A08 | Software and Data Integrity Failures | Medium | 3 |
| A09 | Security Logging and Monitoring Failures | Medium | 4 |
| A10 | Server-Side Request Forgery (SSRF) | **Critical** | 4 |
| | **Total** | | **33** |

**Critical: 2 categories, High: 3 categories, Medium: 4 categories, Low: 1 category**

---

## A01:2021 - Broken Access Control

### Finding A01-1: Unrestricted file path access via CLI arguments (Medium)

**Location:** `scripts/multi_source_scanner.py:78-103`, `scripts/passive_discovery.py:98-103`

**Description:** The `--input`, `--log-dir`, and `--config-dir` CLI arguments accept arbitrary filesystem paths without validation. There is no restriction preventing path traversal (e.g., `--input ../../etc/passwd`) or access to sensitive directories.

```python
# multi_source_scanner.py:82 - No path validation
with open(filepath, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
```

**Risk:** If this tool is exposed via a web interface, API, or shared service, an attacker could read arbitrary files from the system.

**Recommendation:** Validate file paths against an allowlist of directories. Resolve symlinks and verify the canonical path stays within permitted boundaries.

---

### Finding A01-2: Unrestricted network scanning scope (Medium)

**Location:** `scripts/active_probe.py:376-404`

**Description:** The `--network-range` parameter accepts any CIDR range without restriction. Combined with 50 default workers for the `NetworkScanner`, this enables unrestricted scanning of any network reachable from the host.

**Risk:** The tool could be misused to scan networks outside the authorized scope.

**Recommendation:** Implement an allowlist of permitted CIDR ranges. Add a configuration file that defines authorized scan targets.

---

### Finding A01-3: No authorization checks for API gateway admin endpoints (Low)

**Location:** `scripts/multi_source_scanner.py:141-204`

**Description:** The tool connects to Kong (`/services`) and Apigee (`/apis`) admin endpoints. These are typically privileged endpoints. The tool does not verify that the caller is authorized to access these management APIs.

**Risk:** If API keys are present in the environment, the tool will use them without confirming the user's intent or authorization level.

**Recommendation:** Log which gateway admin endpoints are being accessed and require explicit confirmation for admin API access.

---

## A02:2021 - Cryptographic Failures

### Finding A02-1: SSL/TLS certificate verification globally disabled (Critical)

**Location:** `scripts/active_probe.py:187-189, 303-305, 331-333, 348-350`

**Description:** Every HTTPS request made by the active probe disables SSL certificate verification:

```python
# active_probe.py:187-189
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
```

This pattern appears in four separate locations in `active_probe.py` (`_http_request`, and three places in `_detect_documentation`). There is no CLI flag or configuration option to enable verification.

**Risk:** All connections are vulnerable to man-in-the-middle (MITM) attacks. An attacker on the network path could intercept API keys, tokens, and response data.

**Recommendation:** Enable SSL verification by default. Add a `--insecure` flag for cases where self-signed certificates are expected, with a clear warning. Allow users to provide a custom CA bundle via `--ca-bundle`.

---

### Finding A02-2: Credentials transmitted over unverified TLS connections (Critical)

**Location:** `scripts/multi_source_scanner.py:148-153, 184-189`, `scripts/passive_discovery.py:342-346`

**Description:** API credentials (Kong API keys, Apigee Bearer tokens, GitHub tokens, service catalog API keys) are sent in HTTP headers over connections where SSL verification may be disabled. In the `passive_discovery.py` `ServiceCatalogClient`, `urllib.request.urlopen` is used with default SSL context (verification enabled), but the Kong and Apigee scanners in `multi_source_scanner.py` use `urllib.request.urlopen` with no custom context -- which defaults to verifying. However, the `active_probe.py` disables verification on all requests.

**Risk:** Credentials can be intercepted via MITM attacks, especially in the active probe scenario.

**Recommendation:** Never disable SSL verification when transmitting credentials. Separate the "probe insecure endpoints" use case from "authenticate to trusted services."

---

### Finding A02-3: Sensitive output written in plaintext without protection (Low)

**Location:** `scripts/inventory_generator.py:473-477`, `scripts/active_probe.py:494-496`

**Description:** Output files containing discovered API URLs, technology stacks, ownership information, and response samples are written as plaintext JSON/CSV/Markdown with no access control or encryption.

**Risk:** If output files are stored on shared filesystems or committed to version control, sensitive API inventory data could be exposed.

**Recommendation:** Document the sensitivity of output files. Consider file permission restrictions (e.g., `0600`). Optionally support encrypted output.

---

## A03:2021 - Injection

### Finding A03-1: URL injection via unvalidated user input (High)

**Location:** `scripts/multi_source_scanner.py:151, 187, 376, 436`

**Description:** User-supplied values are interpolated directly into URLs without sanitization:

```python
# multi_source_scanner.py:151
services_url = f"{gateway_url.rstrip('/')}/services"

# multi_source_scanner.py:376
url = f"https://api.github.com/orgs/{org}/repos?per_page=100&page={page}"

# multi_source_scanner.py:436
url = f"https://api.github.com/search/code?q=filename:{pattern}+repo:{org}/{repo}"
```

The `--catalog-url` and `--git-org` parameters are not validated. A specially crafted `--git-org` value containing URL metacharacters (e.g., `../../admin`) could manipulate the target URL.

**Risk:** URL manipulation could redirect requests to unintended endpoints or inject query parameters.

**Recommendation:** Validate URL components. Use `urllib.parse.quote()` for path segments. Validate that `--git-org` matches expected patterns (alphanumeric + hyphens).

---

### Finding A03-2: CSV injection in output files (Medium)

**Location:** `scripts/inventory_generator.py:590-618`

**Description:** API names and URLs from untrusted input sources (CSV files, API gateway responses, Git repositories) are written directly to CSV output files without sanitization:

```python
# inventory_generator.py:597-600
writer.writerow([
    e.id, e.name, e.url, e.api_type, e.status,
    e.criticality.get("level", ""), e.discovery_source,
])
```

If a malicious API name or URL contains formula characters (`=`, `+`, `-`, `@`), opening the CSV in Excel or Google Sheets would execute the formula.

**Risk:** An attacker who controls an API catalog entry could inject formulas that execute when a user opens the CSV report.

**Recommendation:** Prefix cell values starting with `=`, `+`, `-`, `@`, `\t`, or `\r` with a single quote (`'`). Alternatively, use a library that handles CSV injection.

---

### Finding A03-3: Log injection via user-controlled data (Low)

**Location:** Throughout all scripts (e.g., `multi_source_scanner.py:98, 100, 134, 172`)

**Description:** User-controlled data (file paths, URLs, API names) is interpolated into log messages using f-strings:

```python
# multi_source_scanner.py:98
self.logger.info(f"Found {len(apis)} APIs in CSV: {filepath}")
```

An attacker who controls a filename or URL could inject newlines or ANSI escape sequences into log output.

**Risk:** Log injection could forge log entries, confuse log analysis, or exploit log viewing tools.

**Recommendation:** Sanitize user-controlled data before logging, or use structured logging (JSON format) that properly escapes special characters.

---

### Finding A03-4: No URL scheme validation (Medium)

**Location:** `scripts/active_probe.py:142-182`

**Description:** The `probe()` method only checks for `repo` and `github` scheme prefixes but accepts any other scheme. URLs with `file://`, `ftp://`, `gopher://`, or other schemes from input files would be processed by `urllib.request`.

```python
# active_probe.py:147-149
if parsed.scheme in ("repo", "github"):
    result.errors.append("Cannot probe non-HTTP URL")
    return result
# All other schemes proceed to _http_request
```

**Risk:** An attacker controlling input URLs could use non-HTTP schemes to access local files or internal services.

**Recommendation:** Explicitly allowlist only `http` and `https` schemes. Reject all others.

---

## A04:2021 - Insecure Design

### Finding A04-1: Response body samples stored in output (Medium)

**Location:** `scripts/active_probe.py:159`

**Description:** The first 500 characters of HTTP response bodies are stored in probe results:

```python
result.response_sample = body[:500] if body else ""
```

This data flows into `probe_results.json`. API responses may contain sensitive data (tokens, PII, internal configurations).

**Risk:** Sensitive data from API responses could be persisted in output files and inadvertently shared.

**Recommendation:** Do not store response body samples by default. Add an opt-in flag (`--include-response-samples`) with a warning about data sensitivity.

---

### Finding A04-2: GraphQL introspection sent to production endpoints (Medium)

**Location:** `scripts/active_probe.py:316-340`

**Description:** The tool sends GraphQL introspection queries to any detected GraphQL endpoint:

```python
introspection_query = json.dumps(
    {"query": "{ __schema { types { name } } }"}
).encode()
```

**Risk:** Introspection queries against production GraphQL APIs may expose the entire API schema, including internal types and fields. Some organizations explicitly disable introspection in production as a security measure.

**Recommendation:** Make GraphQL introspection opt-in via a CLI flag. Document the risk in the README.

---

### Finding A04-3: No scope limitation or target confirmation (Medium)

**Location:** Design-level concern across all scripts

**Description:** The tool has no mechanism to restrict which domains, IPs, or URLs it will probe. There is no confirmation prompt before scanning large network ranges or making requests to external services.

**Risk:** Accidental or intentional scanning of unauthorized targets could violate network policies, terms of service, or laws.

**Recommendation:** Implement a target scope configuration file that defines allowed domains/CIDRs. Add a confirmation prompt for active scanning of large ranges.

---

## A05:2021 - Security Misconfiguration

### Finding A05-1: SSL disabled with no option to enable (High)

**Location:** `scripts/active_probe.py:187-189`

**Description:** SSL verification is hardcoded as disabled in `active_probe.py`. There is no CLI argument, environment variable, or configuration option to enable it. The README documents this as "Configurable (disabled for internal certs)" but no configuration mechanism exists.

**Risk:** Users who need SSL verification cannot enable it. This is a dangerous default that cannot be overridden.

**Recommendation:** Enable SSL by default. Add `--insecure` / `--no-verify-ssl` flag to opt out.

---

### Finding A05-2: Aggressive default thread pool for network scanning (Medium)

**Location:** `scripts/active_probe.py:371`

**Description:** `NetworkScanner` defaults to 50 workers:

```python
def __init__(self, timeout: int = 5, workers: int = 50):
```

Combined with scanning all hosts in a CIDR range across multiple ports, this generates significant network traffic.

**Risk:** Could trigger intrusion detection systems, get the scanning host blocklisted, or cause denial of service on target networks.

**Recommendation:** Reduce default workers for network scanning. Add a `--scan-rate` option. Implement progressive scanning (start slow, increase rate).

---

### Finding A05-3: Overly broad exception handling (Medium)

**Location:** `scripts/multi_source_scanner.py:101, 173, 202, 423`, `scripts/active_probe.py:175, 312, 339, 355, 400`

**Description:** Many critical operations use bare `except Exception` that catches and logs all errors:

```python
# multi_source_scanner.py:173-174
except Exception as e:
    self.logger.error(f"Error connecting to Kong {gateway_url}: {e}")
```

**Risk:** Security-relevant exceptions (SSL errors, authentication failures, permission denials) are treated identically to operational errors. This masks security issues and makes incident investigation difficult.

**Recommendation:** Catch specific exception types. Log security-relevant failures (SSL, auth, permission) at WARNING or CRITICAL level with distinct error codes.

---

### Finding A05-4: Debug-level information in default logging (Low)

**Location:** `scripts/multi_source_scanner.py:34-37`, `scripts/active_probe.py:35-38`

**Description:** Logging is configured at INFO level by default and includes URLs, file paths, and connection details. While DEBUG-level spec parsing errors are appropriately suppressed (line 338), operational logs at INFO level still contain potentially sensitive information.

**Risk:** Default log output may reveal internal infrastructure details (API URLs, gateway addresses, network topology).

**Recommendation:** Review logged data for sensitivity. Consider a `--quiet` mode that suppresses detailed URL logging.

---

## A06:2021 - Vulnerable and Outdated Components

### Finding A06-1: No dependency pinning or lockfile (Low)

**Location:** `api-discovery-plugin/requirements.txt`

**Description:** The requirements file specifies only `pyyaml>=6.0` with no upper bound. Optional dependencies are commented out with minimum versions only. There is no lockfile (`requirements.lock`, `poetry.lock`, `Pipfile.lock`).

```
pyyaml>=6.0
# requests>=2.31.0   (optional)
```

**Risk:** Future installs may pull different versions, potentially including versions with known vulnerabilities.

**Recommendation:** Pin exact versions or use version ranges with upper bounds. Generate and commit a lockfile.

---

### Finding A06-2: No dependency vulnerability scanning (Low)

**Location:** Project-wide

**Description:** There is no configuration for dependency vulnerability scanning tools (e.g., `pip-audit`, `safety`, Dependabot, Snyk).

**Risk:** Vulnerable dependency versions could be installed without detection.

**Recommendation:** Add `pip-audit` to the development workflow. Configure GitHub Dependabot or similar for automated vulnerability monitoring.

---

## A07:2021 - Identification and Authentication Failures

### Finding A07-1: Credentials sent without TLS verification (High)

**Location:** `scripts/multi_source_scanner.py:148-153, 184-189, 371-372`, `scripts/passive_discovery.py:342-346`

**Description:** Four different credential types are transmitted in HTTP headers:

| Credential | Header | File:Line |
|-----------|--------|-----------|
| Kong API key | `apikey` | multi_source_scanner.py:149 |
| Apigee Bearer token | `Authorization: Bearer` | multi_source_scanner.py:185 |
| GitHub token | `Authorization: token` | multi_source_scanner.py:372 |
| Catalog API key | `Authorization: Bearer` | passive_discovery.py:343 |

While `multi_source_scanner.py` and `passive_discovery.py` use default SSL context (verification enabled), there is no explicit enforcement that these requests must use HTTPS. If a user supplies `http://` URLs, credentials will be sent in plaintext.

**Risk:** Credentials could be intercepted if the target URL uses HTTP or if a MITM downgrades the connection.

**Recommendation:** Enforce HTTPS for any request that includes authentication credentials. Reject HTTP URLs when credentials are configured.

---

### Finding A07-2: No token scope validation for GitHub (Medium)

**Location:** `scripts/multi_source_scanner.py:640`

**Description:** The `GITHUB_TOKEN` from the environment is used directly without checking its scope. The tool only needs `repo:read` access, but would work with tokens that have `repo:write`, `admin:org`, or other privileged scopes.

```python
token = os.environ.get("GITHUB_TOKEN")
```

**Risk:** If the token has excessive permissions, compromising the tool or its output could expose elevated access.

**Recommendation:** Document minimum required token permissions. Optionally verify token scopes via the GitHub API before use.

---

### Finding A07-3: No credential masking in error messages (Medium)

**Location:** `scripts/multi_source_scanner.py:173, 202`

**Description:** When connections to Kong or Apigee fail, the error message includes the full URL:

```python
self.logger.error(f"Error connecting to Kong {gateway_url}: {e}")
```

If the URL contains inline credentials (e.g., `https://user:pass@host/`), they would be logged.

**Risk:** Credentials embedded in URLs could appear in log output.

**Recommendation:** Parse and redact credentials from URLs before logging.

---

## A08:2021 - Software and Data Integrity Failures

### Finding A08-1: Untrusted data from external APIs used without validation (Medium)

**Location:** `scripts/multi_source_scanner.py:154-170, 189-199`, `scripts/active_probe.py:154-164`

**Description:** JSON responses from Kong, Apigee, GitHub, and probed APIs are deserialized and used directly to construct `DiscoveredAPI` objects:

```python
# multi_source_scanner.py:154
data = json.loads(response.read().decode())
for svc in data.get("data", []):
    url = f"{svc.get('protocol', 'https')}://{svc.get('host', '')}..."
```

A compromised API gateway could return malicious data that propagates into URLs, names, and metadata throughout the inventory.

**Risk:** Malicious API responses could inject data into the inventory, potentially leading to further exploitation when the inventory is consumed by downstream tools.

**Recommendation:** Validate and sanitize data from external APIs. Enforce expected types and value patterns (e.g., URL format, hostname format).

---

### Finding A08-2: YAML parsing of untrusted repository files (Low)

**Location:** `scripts/multi_source_scanner.py:314-319`

**Description:** YAML files from scanned Git repositories are parsed:

```python
import yaml
spec = yaml.safe_load(f)
```

Using `yaml.safe_load()` is correct and prevents arbitrary code execution. However, parsed data (URLs, server addresses) from these specs is used directly to construct `DiscoveredAPI` objects.

**Risk:** A malicious repository could include an OpenAPI spec with crafted URLs that propagate through the inventory. The YAML parsing itself is safe.

**Recommendation:** Validate URLs extracted from parsed YAML specs before using them.

---

### Finding A08-3: No integrity verification for input files (Low)

**Location:** `scripts/multi_source_scanner.py:78-139`, `scripts/inventory_generator.py:295-305`

**Description:** Input CSV/JSON files and intermediate result files are loaded without any integrity verification (checksums, signatures).

**Risk:** If an attacker can modify input files between stages of the pipeline, they could inject malicious data into the final inventory.

**Recommendation:** For multi-stage pipelines, consider adding checksum verification between stages.

---

## A09:2021 - Security Logging and Monitoring Failures

### Finding A09-1: No security event logging (Medium)

**Location:** All scripts

**Description:** The logging infrastructure captures operational events (scan progress, errors) but does not distinguish security-relevant events. There is no specific logging for:
- Authentication attempts (success/failure)
- Access to sensitive resources
- Network scanning activity
- Rate limit triggers

**Risk:** Security incidents cannot be detected or investigated from the current logs.

**Recommendation:** Implement structured security event logging. Log authentication events, scanning scope, and rate limit enforcement separately from operational logs.

---

### Finding A09-2: No audit trail for scanning activity (Medium)

**Location:** Design-level concern

**Description:** There is no persistent audit log of what was scanned, when, by whom, and with what parameters. The only record is transient console output.

**Risk:** Without an audit trail, it's impossible to determine what networks or systems were scanned, making incident response and compliance difficult.

**Recommendation:** Write a machine-readable audit log entry for each scan execution, including: timestamp, user, parameters, targets, and results summary.

---

### Finding A09-3: Security exceptions treated as operational errors (Medium)

**Location:** `scripts/active_probe.py:167-180`

**Description:** HTTP errors (including 401 Unauthorized, 403 Forbidden) are handled identically to connection errors:

```python
except HTTPError as e:
    result.reachable = True
    result.status_code = e.code
    result.errors.append(f"HTTP {e.code}: {e.reason}")
```

401/403 responses indicate authorization issues that warrant different handling than 404 or 500 errors.

**Risk:** Authentication and authorization failures during scanning are not flagged for review.

**Recommendation:** Log 401/403 responses as security events. Flag APIs requiring authentication in the output.

---

### Finding A09-4: Rate limiter activity not logged (Low)

**Location:** `scripts/active_probe.py:63-85`

**Description:** The `RateLimiter` class throttles requests silently. When rate limiting is triggered, there is no log entry.

**Risk:** Inability to diagnose scan performance issues or detect when rate limiting is actively protecting targets.

**Recommendation:** Log when rate limiting causes delays, including the target host and wait duration.

---

## A10:2021 - Server-Side Request Forgery (SSRF)

### Finding A10-1: SSRF via --catalog-url parameter (Critical)

**Location:** `scripts/multi_source_scanner.py:141-204`

**Description:** The `--catalog-url` argument is passed directly to HTTP request functions without any URL validation:

```python
# multi_source_scanner.py:151
services_url = f"{gateway_url.rstrip('/')}/services"
req = urllib.request.Request(services_url, headers=headers)
with urllib.request.urlopen(req, timeout=30) as response:
```

An attacker could supply:
- `--catalog-url http://169.254.169.254/latest/meta-data` (AWS metadata)
- `--catalog-url http://localhost:6379` (internal Redis)
- `--catalog-url http://10.0.0.1:8500` (internal Consul)

**Risk:** If the tool runs in a cloud environment or internal network, SSRF could expose cloud metadata credentials, internal service data, or enable lateral movement.

**Recommendation:** Implement URL validation:
1. Block private/reserved IP ranges (10.x, 172.16-31.x, 192.168.x, 169.254.x, 127.x)
2. Block cloud metadata endpoints
3. Resolve DNS and validate the resolved IP
4. Maintain an allowlist of permitted domains

---

### Finding A10-2: SSRF via URLs in input files (Critical)

**Location:** `scripts/active_probe.py:460-469, 142-182`

**Description:** URLs loaded from input JSON files (`--urls-file`) are probed directly:

```python
# active_probe.py:464-469
with open(args.urls_file, "r") as f:
    data = json.load(f)
    if isinstance(data, list):
        urls.extend(data)
    elif "apis" in data:
        urls.extend(api.get("url", "") for api in data["apis"] if api.get("url"))
```

These URLs are then passed to `probe()` which makes HTTP requests. An attacker who can influence the input file can direct the tool to make requests to arbitrary internal endpoints.

**Risk:** This is the highest-risk SSRF vector because input files may come from untrusted sources (API catalogs, shared drives).

**Recommendation:** Apply the same URL validation as A10-1. Add a `--allowed-domains` parameter. Resolve hostnames and block internal IPs.

---

### Finding A10-3: SSRF via service catalog URL (High)

**Location:** `scripts/passive_discovery.py:345-346`

**Description:** The `ServiceCatalogClient` makes requests to a user-supplied URL:

```python
req = urllib.request.Request(self.catalog_url, headers=headers)
with urllib.request.urlopen(req, timeout=30) as response:
```

**Risk:** Same SSRF risk as A10-1, compounded by the fact that this request includes authentication headers.

**Recommendation:** Apply URL validation and block requests to internal/metadata endpoints.

---

### Finding A10-4: DNS rebinding not mitigated (Medium)

**Location:** All HTTP request locations

**Description:** None of the HTTP request paths validate the resolved IP address after DNS resolution. An attacker could register a domain that initially resolves to an allowed IP but then rebinds to an internal address.

**Risk:** DNS rebinding could bypass domain-based allowlists.

**Recommendation:** Resolve DNS, validate the IP, then connect to the validated IP directly (pin the resolution).

---

## Remediation Priority

### Immediate (Critical)

1. **A02-1:** Enable SSL verification by default, add `--insecure` opt-out flag
2. **A10-1, A10-2, A10-3:** Implement URL validation with IP blocklist for all HTTP request paths

### Short-term (High)

3. **A03-1:** Validate and sanitize URL components from user input
4. **A05-1:** Make SSL verification configurable (not hardcoded disabled)
5. **A07-1:** Enforce HTTPS for authenticated requests

### Medium-term (Medium)

6. **A01-1:** Validate file paths against allowed directories
7. **A03-2:** Sanitize CSV output against formula injection
8. **A04-1:** Make response body sampling opt-in
9. **A05-3:** Use specific exception types instead of bare `except Exception`
10. **A09-1:** Implement structured security event logging
11. **A09-2:** Add persistent audit trail for scan activity

### Long-term (Low)

12. **A06-1:** Pin dependency versions and add lockfile
13. **A06-2:** Add automated dependency vulnerability scanning
14. **A08-2:** Validate data from parsed YAML specs
15. **A09-4:** Log rate limiter activity

# Versioning Analyzer Skill

## Purpose
Analyzes API versioning strategy and consistency across the API estate.

## Versioning Strategies

### URL Path Versioning
```
https://api.example.com/v1/users
https://api.example.com/v2/users
```
**Detection:** `/v\d+/` pattern in paths

### Query Parameter Versioning
```
https://api.example.com/users?version=1
https://api.example.com/users?api-version=2021-01-01
```
**Detection:** `version` or `api-version` query parameter

### Header Versioning
```
Accept: application/vnd.example.v1+json
X-API-Version: 2
```
**Detection:** Version in Accept header or custom version header

### No Versioning
API has no explicit versioning strategy.

## Analysis Rules

| Rule ID | Severity | Description |
|---------|----------|-------------|
| `version-strategy-present` | warning | API should have explicit versioning |
| `version-strategy-consistent` | warning | Use same strategy across all APIs |
| `version-in-info` | info | info.version should match URL version |
| `version-format-semver` | info | Prefer semantic versioning (x.y.z) |
| `version-documented` | warning | Versioning policy should be documented |

## Version Extraction

```python
def extract_version(spec, servers):
    # From URL paths
    for path in spec.get('paths', {}):
        match = re.search(r'/v(\d+)/', path)
        if match:
            return {'strategy': 'url_path', 'version': match.group(1)}

    # From servers
    for server in servers:
        match = re.search(r'/v(\d+)', server.get('url', ''))
        if match:
            return {'strategy': 'url_path', 'version': match.group(1)}

    # From info.version
    info_version = spec.get('info', {}).get('version')
    if info_version:
        return {'strategy': 'info_only', 'version': info_version}

    return {'strategy': 'none', 'version': None}
```

## Output Format

```json
{
  "api_name": "Payment API",
  "versioning": {
    "strategy": "url_path",
    "current_version": "2",
    "info_version": "2.1.0",
    "all_versions_found": ["v1", "v2"],
    "issues": [
      {
        "rule": "version-format-semver",
        "severity": "info",
        "message": "URL version 'v2' doesn't match semver in info '2.1.0'"
      }
    ]
  }
}
```

## Fleet Analysis

When analyzing multiple APIs:

```json
{
  "fleet_versioning": {
    "strategies_used": {
      "url_path": 45,
      "header": 3,
      "query_param": 2,
      "none": 10
    },
    "dominant_strategy": "url_path",
    "consistency_score": 75,
    "recommendation": "Standardize on URL path versioning"
  }
}
```

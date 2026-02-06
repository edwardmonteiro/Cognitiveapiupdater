# Deprecation Tracker Skill

## Purpose
Identifies deprecated endpoints, tracks sunset timelines, and monitors usage of deprecated APIs.

## Deprecation Markers

### OpenAPI Standard
```yaml
paths:
  /old-endpoint:
    get:
      deprecated: true
      x-sunset-date: "2024-12-31"
      description: "DEPRECATED: Use /new-endpoint instead"
```

### Common Patterns Detected

| Pattern | Location | Example |
|---------|----------|---------|
| `deprecated: true` | Operation | OpenAPI standard |
| `x-deprecated` | Operation | Custom extension |
| `x-sunset-date` | Operation | Sunset date |
| `x-deprecated-since` | Operation | Version deprecated |
| `x-replacement` | Operation | Alternative endpoint |
| `DEPRECATED` | Description | Text marker |
| `/legacy/` | Path | Path pattern |
| `/old/` | Path | Path pattern |

## Analysis Rules

| Rule ID | Severity | Description |
|---------|----------|-------------|
| `deprecated-no-sunset` | warning | Deprecated endpoint has no sunset date |
| `deprecated-no-replacement` | warning | No replacement endpoint documented |
| `sunset-date-past` | error | Sunset date has passed |
| `sunset-date-soon` | warning | Sunset within 90 days |
| `deprecated-still-traffic` | warning | Deprecated endpoint receiving traffic |
| `deprecated-high-traffic` | error | Deprecated endpoint with high traffic |

## Output Format

```json
{
  "deprecated_endpoints": [
    {
      "path": "/v1/users/{id}",
      "method": "GET",
      "deprecated_since": "2023-06-01",
      "sunset_date": "2024-06-01",
      "replacement": "/v2/users/{id}",
      "status": "sunset_soon",
      "days_until_sunset": 45,
      "traffic": {
        "has_traffic_data": true,
        "daily_requests": 1500,
        "unique_clients": 12,
        "trend": "declining"
      },
      "issues": [
        {
          "rule": "sunset-date-soon",
          "severity": "warning",
          "message": "Endpoint sunset in 45 days but still has 1500 daily requests"
        }
      ],
      "migration_status": {
        "replacement_available": true,
        "migration_guide_url": null,
        "breaking_changes": ["Response schema changed", "Auth method changed"]
      }
    }
  ],
  "summary": {
    "total_deprecated": 15,
    "with_sunset_date": 12,
    "without_sunset_date": 3,
    "past_sunset": 2,
    "sunset_within_90_days": 4,
    "still_receiving_traffic": 10
  }
}
```

## Migration Tracking

Track client migration progress:

```json
{
  "migration_progress": {
    "endpoint": "/v1/payments",
    "replacement": "/v2/payments",
    "sunset_date": "2024-06-01",
    "client_migration": {
      "total_clients": 25,
      "migrated": 18,
      "in_progress": 4,
      "not_started": 3,
      "migration_percentage": 72
    },
    "traffic_shift": {
      "old_endpoint_percentage": 35,
      "new_endpoint_percentage": 65,
      "trend": "migrating"
    }
  }
}
```

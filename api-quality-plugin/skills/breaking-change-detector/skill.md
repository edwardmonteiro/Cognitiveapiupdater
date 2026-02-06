# Breaking Change Detector Skill

## Purpose
Detects breaking changes between OpenAPI spec versions to prevent unintended client disruption.

## Breaking Change Categories

### Removals (Always Breaking)

| Change | Severity | Description |
|--------|----------|-------------|
| Path removed | error | Endpoint no longer exists |
| Method removed | error | HTTP method removed from path |
| Required param removed server-side | - | OK (less required from client) |
| Response field removed | error | Client may depend on field |
| Enum value removed | error | Client may send removed value |
| Security scheme removed | error | Client auth may break |

### Additions

| Change | Severity | Description |
|--------|----------|-------------|
| Required param added | error | Client must update requests |
| Required field added (request) | error | Client must send new field |
| Required field added (response) | - | OK (additive) |
| New path added | - | OK (additive) |
| New method added | - | OK (additive) |
| Optional param added | - | OK (additive) |

### Modifications

| Change | Severity | Description |
|--------|----------|-------------|
| Param type changed | error | Client format may break |
| Response type changed | error | Client parsing may break |
| Param made required | error | Previously optional now required |
| Max length decreased | warning | Valid requests may be rejected |
| Min length increased | warning | Valid requests may be rejected |
| Pattern changed | warning | Valid values may be rejected |
| Enum values changed | error | Client may send invalid values |

### Compatibility Safe Changes

These changes are generally safe:
- Adding optional fields to responses
- Adding new endpoints
- Adding new optional parameters
- Relaxing validation (increasing maxLength, etc.)
- Adding new enum values (server-side)
- Adding new response codes

## Detection Process

```python
def compare_specs(old_spec, new_spec):
    changes = []

    # Compare paths
    old_paths = set(old_spec.get('paths', {}).keys())
    new_paths = set(new_spec.get('paths', {}).keys())

    removed_paths = old_paths - new_paths
    for path in removed_paths:
        changes.append({
            'type': 'path_removed',
            'severity': 'error',
            'breaking': True,
            'path': path
        })

    # Compare operations in common paths
    for path in old_paths & new_paths:
        compare_operations(old_spec, new_spec, path, changes)

    return changes
```

## Output Format

```json
{
  "comparison": {
    "old_version": "1.2.0",
    "new_version": "2.0.0",
    "old_spec": "payment-api-v1.yaml",
    "new_spec": "payment-api-v2.yaml"
  },
  "summary": {
    "total_changes": 15,
    "breaking_changes": 5,
    "non_breaking_changes": 10,
    "is_major_version_required": true
  },
  "breaking_changes": [
    {
      "type": "required_param_added",
      "severity": "error",
      "path": "paths./payments.post.parameters",
      "description": "New required parameter 'idempotencyKey' added",
      "old_value": null,
      "new_value": {
        "name": "idempotencyKey",
        "in": "header",
        "required": true
      },
      "impact": "All clients must update to send this header",
      "migration_guide": "Add 'Idempotency-Key' header with UUID to all POST /payments requests"
    }
  ],
  "non_breaking_changes": [
    {
      "type": "optional_field_added",
      "severity": "info",
      "path": "components.schemas.PaymentResponse.properties.metadata",
      "description": "New optional field 'metadata' added to response",
      "impact": "None - additive change"
    }
  ],
  "recommendations": [
    "This release contains breaking changes - bump to v2.0.0",
    "Provide migration guide for idempotencyKey header",
    "Consider deprecation period before removing v1"
  ]
}
```

## Semver Recommendation

Based on changes detected:

| Changes | Recommended Version Bump |
|---------|-------------------------|
| Only additive | Minor (1.0.0 → 1.1.0) |
| Bug fixes only | Patch (1.0.0 → 1.0.1) |
| Any breaking change | Major (1.0.0 → 2.0.0) |

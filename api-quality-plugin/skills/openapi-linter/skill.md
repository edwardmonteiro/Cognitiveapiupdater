# OpenAPI Linter Skill

## Purpose
Validates OpenAPI specifications against the OpenAPI 3.x standard and configurable rulesets.

## Rulesets

### Minimal
Basic validity checks only:
- Valid JSON/YAML syntax
- OpenAPI version present
- Info object present
- At least one path defined

### Standard (default)
Minimal + best practices:
- All operations have operationId
- All operations have description
- All parameters have description
- All responses have description
- Security schemes defined
- Tags are used consistently

### Strict
Standard + enterprise requirements:
- All operations have examples
- All error responses documented (400, 401, 403, 404, 500)
- Pagination required for list operations
- Rate limit headers documented
- Contact info required
- License required

## Rules

| Rule ID | Severity | Description |
|---------|----------|-------------|
| `openapi-version` | error | OpenAPI version must be 3.x |
| `info-required` | error | Info object is required |
| `info-title` | error | Info must have title |
| `info-version` | error | Info must have version |
| `paths-required` | error | At least one path required |
| `operation-operationId` | warning | Operations should have operationId |
| `operation-description` | warning | Operations should have description |
| `operation-tags` | info | Operations should have tags |
| `parameter-description` | warning | Parameters should have description |
| `response-description` | warning | Responses should have description |
| `schema-properties-description` | info | Schema properties should have description |
| `no-eval-in-schema` | error | No dangerous patterns in schema |
| `valid-schema-ref` | error | All $ref must resolve |
| `no-unused-components` | info | Components should be referenced |

## Output Format

```json
{
  "rule": "operation-description",
  "severity": "warning",
  "message": "Operation GET /users is missing description",
  "path": "paths./users.get",
  "location": {"line": 23, "column": 5},
  "fix_suggestion": "Add 'description' field to the operation"
}
```

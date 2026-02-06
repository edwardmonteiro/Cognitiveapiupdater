# /audit-api - API Specification Audit Command

## Description

Audits API specifications (OpenAPI, WSDL) for quality issues, security gaps, naming convention violations, versioning problems, and governance compliance. Supports single-spec and bulk inventory modes.

## Usage

```bash
# Audit a single OpenAPI spec
/audit-api --spec openapi.yaml

# Audit all APIs in an inventory
/audit-api --inventory api_inventory.json

# Audit with custom policy
/audit-api --inventory api_inventory.json --policy corporate-policy.yaml

# Only show errors (skip warnings/info)
/audit-api --spec openapi.yaml --severity error

# Run specific rules only
/audit-api --spec openapi.yaml --rules naming,security
```

## Audit Categories

### 1. OpenAPI Linting
Validates spec structure and completeness:
- Required fields present (info, paths, components)
- Valid HTTP methods and status codes
- Schema definitions complete (no empty objects)
- Descriptions present on operations and parameters
- Examples provided for request/response bodies
- Response codes follow HTTP semantics (201 for POST create, 204 for DELETE)

### 2. Naming Conventions
Enforces consistent naming:
- Path segments: `kebab-case` (e.g., `/payment-orders`)
- Query parameters: `camelCase` or `snake_case` (configurable)
- Schema properties: `camelCase`
- Schema names: `PascalCase`
- No abbreviations in paths (e.g., `/txn` should be `/transaction`)
- Consistent pluralization for collections

### 3. Security Checks
Detects security issues:
- Missing security schemes definition
- Endpoints without authentication requirements
- HTTP (not HTTPS) server URLs
- PII fields without `x-sensitive` marker
- Missing rate limiting headers documentation
- Overly permissive CORS configuration
- Missing input validation (pattern, maxLength, enum)

### 4. Versioning Analysis
Checks versioning consistency:
- Version present in URL path or header
- Consistent versioning strategy across APIs
- Semantic versioning compliance (major.minor.patch)
- Version documented in info.version
- No mixed versioning strategies

### 5. Deprecation Tracking
Identifies deprecation issues:
- Deprecated operations without sunset date
- Deprecated schemas still referenced
- Missing migration guide for deprecated endpoints
- Deprecated APIs still receiving traffic (from logs)

### 6. Breaking Change Detection
Compares versions for compatibility:
- Removed endpoints or methods
- Changed required parameters
- Modified response schema (removed fields)
- Changed authentication requirements
- Changed error response format

## Workflow

```
1. LOAD: Read spec files (OpenAPI YAML/JSON, WSDL XML)
2. PARSE: Validate structure and extract metadata
3. LINT: Run openapi-linter rules
4. NAMING: Check naming-conventions rules
5. SECURITY: Run security-checker rules
6. VERSIONING: Run versioning-analyzer rules
7. DEPRECATION: Run deprecation-tracker rules
8. BREAKING: Run breaking-change-detector rules (if previous version available)
9. SCORE: Calculate compliance score (0-100)
10. OUTPUT: Generate results JSON, report MD, remediation plan
```

## Output

### Console Summary
```
API Audit Complete!

Specs audited: 650
Total issues found: 3,200

By severity:
- Errors: 450 (14%)
- Warnings: 1,800 (56%)
- Info: 950 (30%)

By category:
- Linting: 800
- Naming: 600
- Security: 500
- Versioning: 400
- Deprecation: 300
- Breaking changes: 600

Compliance score: 62/100

Top issues:
1. Missing operation descriptions (420 occurrences)
2. Endpoints without auth requirement (380)
3. Inconsistent naming conventions (350)
```

### Files Generated
- `audit_results.json` - Detailed findings per API
- `audit_report.md` - Human-readable report
- `remediation_plan.md` - Prioritized fix plan
- `fixes/` - Auto-generated fix suggestions

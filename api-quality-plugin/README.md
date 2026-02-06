# API Quality & Governance Toolkit

A Claude Code plugin for auditing API specifications, enforcing organizational standards, and generating improvement roadmaps.

## Purpose

After discovering APIs (using the API Discovery Plugin), this toolkit helps you:

1. **Audit** - Validate OpenAPI specs against quality rules
2. **Score** - Calculate governance compliance scores
3. **Plan** - Generate prioritized remediation plans

## Quick Start

```bash
# Audit a single spec
python scripts/spec_auditor.py --spec openapi.yaml

# Audit from inventory
python scripts/spec_auditor.py --inventory ../api-discovery-plugin/output/api_inventory.json

# Generate governance scores
python scripts/governance_scorer.py \
  --inventory ../api-discovery-plugin/output/api_inventory.json \
  --audit audit-output/audit_results.json

# Generate remediation plan
python scripts/remediation_generator.py \
  --audit audit-output/audit_results.json \
  --governance governance-output/governance_scorecard.json
```

## Components

### Commands

| Command | Description |
|---------|-------------|
| `/audit-api` | Audit specs for quality, security, and compliance |
| `/governance-report` | Generate governance compliance report |

### Skills

| Skill | Description |
|-------|-------------|
| `openapi-linter` | Validate against OpenAPI 3.x standard |
| `naming-conventions` | Check path, param, schema naming |
| `security-checker` | Detect auth issues, PII exposure |
| `versioning-analyzer` | Analyze versioning strategy |
| `deprecation-tracker` | Track deprecated endpoints |
| `breaking-change-detector` | Detect breaking changes between versions |

### Scripts

| Script | Description |
|--------|-------------|
| `spec_auditor.py` | Main audit engine |
| `governance_scorer.py` | Multi-dimensional scoring |
| `remediation_generator.py` | Prioritized fix planning |

## Audit Checks

### Linting
- Valid OpenAPI 3.x structure
- Required fields present
- Valid $ref references
- Consistent tag usage

### Naming
- Path segments: `kebab-case`
- Parameters: `camelCase`
- Schemas: `PascalCase`
- Properties: `camelCase`

### Security
- Authentication schemes defined
- Operations have security requirements
- HTTPS required
- No credentials in URLs
- PII fields documented

### Documentation
- Operation descriptions
- Parameter descriptions
- Response descriptions
- Error responses (4xx, 5xx)

## Governance Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Documentation | 25% | OpenAPI spec completeness |
| Security | 25% | Auth, validation, PII |
| Standards | 20% | Naming, versioning, errors |
| Ownership | 15% | Owner assigned, contact |
| Lifecycle | 15% | Status, deprecation |

## Output Files

```
audit-output/
├── audit_results.json    # Detailed findings
└── audit_report.md       # Human-readable report

governance-output/
├── governance_scorecard.json  # Scores per API
└── governance_report.md       # Executive summary

remediation-output/
├── remediation_plan.json  # Prioritized items
└── remediation_plan.md    # Actionable plan
```

## Integration

Works with the API Discovery Plugin:

```bash
# 1. Discover APIs
cd ../api-discovery-plugin
python scripts/multi_source_scanner.py --input apis.csv

# 2. Audit discovered APIs
cd ../api-quality-plugin
python scripts/spec_auditor.py --inventory ../api-discovery-plugin/output/api_inventory.json
```

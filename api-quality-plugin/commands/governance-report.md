# /governance-report - API Governance Compliance Report

## Description

Generates an executive-level governance compliance report for an API estate. Combines discovery inventory data with audit results to produce a comprehensive view of API governance maturity.

## Usage

```bash
# Generate from inventory + run fresh audit
/governance-report --inventory api_inventory.json

# Generate from inventory + existing audit
/governance-report --inventory api_inventory.json --audit-results audit_results.json

# Generate with custom policy
/governance-report --inventory api_inventory.json --policy corporate-policy.yaml
```

## Report Sections

### 1. Executive Summary
- Total APIs, compliance score, trend vs previous report
- Key risks and recommended actions

### 2. Governance Scorecard
Scores by policy dimension:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Documentation | 25% | OpenAPI spec completeness |
| Security | 25% | Auth, input validation, PII protection |
| Standards | 20% | Naming, versioning, error handling |
| Ownership | 15% | Assigned owner, contact info |
| Lifecycle | 15% | Deprecation, sunset dates, status |

### 3. Risk Matrix

```
         High Impact
            │
   Critical │  Major
   (fix now)│  (plan fix)
────────────┼────────────
   Minor    │  Low
   (backlog)│  (monitor)
            │
         Low Impact
     High Likelihood ──── Low Likelihood
```

### 4. Compliance by Squad
Per-squad breakdown showing which teams are most/least compliant.

### 5. Improvement Roadmap
Prioritized remediation plan with estimated effort.

## Output Files

- `governance_report.md` - Full report
- `governance_scorecard.json` - Machine-readable scores
- `remediation_plan.md` - Prioritized actions

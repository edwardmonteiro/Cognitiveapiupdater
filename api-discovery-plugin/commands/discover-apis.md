# /discover-apis - API Discovery & Classification Command

## Description

Discovers, classifies, and generates a complete inventory of APIs from multiple sources. Supports passive analysis (catalogs, logs) and active probing (network scanning, endpoint testing).

## Prerequisites

- Python 3.9+
- Required packages: `pip install -r requirements.txt`
- Network access to target APIs (for active mode)
- Credentials configured for API gateways/Git repos (if applicable)

## Usage

```bash
# Basic: Analyze a CSV/JSON file with API list
/discover-apis --input apis.csv

# Multi-source discovery
/discover-apis --sources catalog,git,logs \
  --catalog-url https://api-gateway.example.com/catalog \
  --git-org my-organization \
  --log-dir /var/log/nginx/

# Active network discovery
/discover-apis --mode active \
  --network-range 10.0.0.0/16 \
  --ports 80,443,8080,3000

# Passive analysis only
/discover-apis --mode passive \
  --sources logs \
  --log-dir /var/log/api-gateway/
```

## Workflow

The command executes the following phases sequentially:

### Phase 1: Input Collection
- Validate provided arguments
- Check source availability
- Verify credentials and connectivity
- Confirm discovery mode with user

### Phase 2: Multi-Source Discovery
- Execute `multi_source_scanner.py` to collect API URLs from all specified sources
- Deduplicate discovered APIs (same API found in multiple sources)
- Generate `raw_apis.json` with all discovered URLs

**Sources supported:**
| Source | Description | Required Args |
|--------|-------------|---------------|
| `catalog` | API catalogs, gateways (Kong, Apigee), CMDB | `--catalog-url` or `--input` |
| `git` | GitHub/GitLab repositories | `--git-org` |
| `logs` | Access logs (nginx, Apache, API gateway) | `--log-dir` |
| `network` | Active network scanning | `--network-range`, `--ports` |

### Phase 3: API Classification
For each discovered API, invoke the **api-classifier** agent:
- Detect API type: REST, GraphQL, SOAP, gRPC
- Apply pattern recognition rules
- Confidence scoring for classification

### Phase 4: Documentation Detection
For each API, based on its type:
- **REST** -> invoke `openapi-detector` skill
- **GraphQL** -> invoke `graphql-introspection` skill
- **SOAP** -> invoke `soap-wsdl-parser` skill
- Extract metadata from discovered specs

### Phase 5: Technology Analysis
For each API, invoke the **tech-analyzer** agent:
- Analyze HTTP response headers
- Fingerprint framework and language
- Detect cloud infrastructure provider

### Phase 6: Ownership Discovery
For each API, invoke the **ownership-finder** agent:
- Check OpenAPI spec `info.contact`
- Search Git repos for CODEOWNERS
- Query CMDB/service catalog
- Infer from URL patterns

### Phase 7: Criticality Scoring
For each API, invoke the **criticality-scorer** agent:
- Analyze request volume (from logs)
- Check external exposure
- Classify data sensitivity
- Calculate composite score (0-100)

### Phase 8: Inventory Generation
- Execute `inventory_generator.py`
- Aggregate all results into final inventory
- Generate summary statistics
- Identify problematic APIs (orphaned, undocumented, shadow)

### Phase 9: Output
Generate the following files:
- `api_inventory.json` - Complete inventory
- `discovery_report.md` - Executive report
- `orphaned_apis.csv` - APIs without owners
- `undocumented_apis.csv` - APIs without documentation

## Output Format

### Console Summary
```
API Discovery Complete!

Statistics:
- Total APIs discovered: N
- Sources used: [list]

Distribution:
- REST: N (X%)
- GraphQL: N (X%)
- SOAP: N (X%)
- gRPC: N (X%)

Documentation:
- With OpenAPI: N (X%)
- Without docs: N (X%)

Ownership:
- With owner: N (X%)
- Orphaned: N (X%)

Criticality:
- High: N (X%)
- Medium: N (X%)
- Low: N (X%)
```

### JSON Inventory Schema
See `inventory_generator.py` for the complete JSON schema.

## Configuration

Default settings can be overridden via arguments:

| Setting | Default | Description |
|---------|---------|-------------|
| `--workers` | 20 | Parallel workers |
| `--timeout` | 30 | Seconds per API |
| `--output` | `./output` | Output directory |
| `--mode` | passive | Discovery mode |

## Error Handling

- Network failures: 3 retries with exponential backoff
- Timeout per API: Configurable (default 30s)
- Failed APIs are logged but don't block overall discovery
- Progress is saved incrementally for resume capability

## Security

- Credentials are never logged
- `robots.txt` is respected in active mode
- Rate limiting: max 10 requests/second per host
- Active network scanning requires explicit `--mode active` flag

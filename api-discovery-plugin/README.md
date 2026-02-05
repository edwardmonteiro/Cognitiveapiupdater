# API Discovery & Classification Plugin

A Claude Code plugin that discovers, classifies, and inventories APIs from multiple sources. Designed for organizations managing large API estates with limited visibility.

## Problem

When inheriting hundreds or thousands of APIs from legacy systems, you need answers to:

- How many APIs actually exist?
- What type are they (REST, GraphQL, SOAP, gRPC)?
- Do they have documentation (OpenAPI, WSDL)?
- What technology do they use (Java, Python, Node.js)?
- Who owns them (squad, department)?
- How critical are they?
- What is their current status (active, deprecated)?

**This plugin automates that discovery process.**

## Features

- **Multi-source discovery**: Catalogs, Git repos, access logs, network scanning
- **Automatic classification**: REST, GraphQL, SOAP, gRPC detection with confidence scoring
- **Documentation detection**: OpenAPI/Swagger, WSDL, GraphQL schema
- **Technology fingerprinting**: Language, framework, server, cloud provider
- **Ownership discovery**: OpenAPI contacts, CODEOWNERS, CMDB, URL pattern inference
- **Criticality scoring**: Volume, exposure, data sensitivity, business impact
- **Complete inventory**: JSON inventory, Markdown report, CSV exports

## Quick Start

### Prerequisites

```bash
python3 -m pip install -r requirements.txt
```

### Basic Usage

```bash
# Discover APIs from a CSV/JSON file
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

# Passive log analysis only
/discover-apis --mode passive \
  --sources logs \
  --log-dir /var/log/api-gateway/
```

### Using Scripts Directly

```bash
# Step 1: Scan sources
python scripts/multi_source_scanner.py \
  --sources catalog,git \
  --input apis.csv \
  --output output/raw_apis.json

# Step 2: Active probing
python scripts/active_probe.py \
  --urls-file output/raw_apis.json \
  --output output/probe_results.json

# Step 3: Passive analysis
python scripts/passive_discovery.py \
  --log-dir /var/log/nginx/ \
  --output output/passive_apis.json

# Step 4: Generate inventory
python scripts/inventory_generator.py \
  --raw-apis output/raw_apis.json \
  --probe-results output/probe_results.json \
  --passive-results output/passive_apis.json \
  --output-dir output/
```

## Plugin Structure

```
api-discovery-plugin/
├── .claude-plugin/
│   └── plugin.json              # Plugin configuration
├── commands/
│   └── discover-apis.md         # Main discovery command
├── agents/
│   ├── api-classifier/          # Classifies API type (REST/GraphQL/SOAP/gRPC)
│   ├── spec-detector/           # Detects OpenAPI/WSDL/GraphQL schemas
│   ├── tech-analyzer/           # Identifies technology stack
│   ├── ownership-finder/        # Discovers API ownership
│   └── criticality-scorer/      # Calculates criticality score
├── skills/
│   ├── api-pattern-recognition/ # API type pattern matching rules
│   ├── openapi-detector/        # OpenAPI/Swagger detection
│   ├── graphql-introspection/   # GraphQL schema introspection
│   ├── soap-wsdl-parser/        # WSDL parsing rules
│   └── framework-fingerprinting/# Technology stack detection rules
├── scripts/
│   ├── multi_source_scanner.py  # Multi-source API scanner
│   ├── active_probe.py          # Active endpoint probing
│   ├── passive_discovery.py     # Passive log analysis
│   └── inventory_generator.py   # Final inventory generation
├── requirements.txt
└── README.md
```

## Discovery Sources

| Source | Method | Required Args |
|--------|--------|---------------|
| **Catalog** | Parse CSV/JSON, query API Gateways | `--input` or `--catalog-url` |
| **Git** | Scan repos for OpenAPI specs, project files | `--git-org` or `--git-dir` |
| **Logs** | Analyze access logs for API patterns | `--log-dir` |
| **Network** | Port scanning, service fingerprinting | `--network-range`, `--ports` |

## API Classification

| Type | Detection Method |
|------|-----------------|
| **REST** | URL patterns (`/api/`, `/v1/`), JSON responses, OpenAPI specs |
| **GraphQL** | `/graphql` endpoint, introspection queries, `{"data":...}` responses |
| **SOAP** | `.asmx`/`.svc` endpoints, XML responses, WSDL availability |
| **gRPC** | Port 50051, `application/grpc` content type, HTTP/2 |

## Output Files

| File | Description |
|------|-------------|
| `api_inventory.json` | Complete API inventory with all metadata |
| `discovery_report.md` | Executive summary report |
| `orphaned_apis.csv` | APIs without identified owners |
| `undocumented_apis.csv` | APIs without formal documentation |

## Criticality Scoring

APIs are scored 0-100 based on four weighted factors:

| Factor | Weight | Description |
|--------|--------|-------------|
| Request Volume | 30% | Traffic volume from logs |
| External Exposure | 25% | Public vs internal access |
| Data Sensitivity | 25% | PCI, PII, financial data |
| Business Impact | 20% | Core banking vs analytics |

| Level | Score | Description |
|-------|-------|-------------|
| **High** | 70-100 | Core banking, Open Banking, auth APIs |
| **Medium** | 40-69 | Back-office, internal essential APIs |
| **Low** | 0-39 | Analytics, experimental, deprecated APIs |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `--workers` | 20 | Parallel processing workers |
| `--timeout` | 30s | Timeout per API probe |
| `--mode` | passive | Discovery mode (passive/active/hybrid) |
| `--output` | `./output` | Output directory |

## Security

- **Passive by default**: Active network scanning requires explicit `--mode active`
- **Rate limiting**: Max 10 requests/second per host
- **No credential logging**: Credentials are never written to output files
- **robots.txt respected**: Active probing respects robots.txt
- **SSL verification**: Configurable (disabled for internal certs)

## Input File Format

### CSV
```csv
name,url,type,owner
Payment API,https://api.example.com/v1/payments,REST,Payments Squad
Account API,https://api.example.com/v1/accounts,REST,Accounts Squad
```

### JSON
```json
{
  "apis": [
    {"name": "Payment API", "url": "https://api.example.com/v1/payments"},
    {"name": "Account API", "url": "https://api.example.com/v1/accounts"}
  ]
}
```

## License

Apache License 2.0

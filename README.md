# Cognitiveapiupdater

A collection of Claude Code plugins for API lifecycle management -- from discovery through quality governance to real-time catalog access. Built for engineering organizations managing large API estates with limited visibility.

## The Problem

Enterprise organizations inherit hundreds or thousands of APIs with zero visibility:

- No single inventory of what exists
- Unknown API types, tech stacks, and ownership
- Missing or outdated documentation
- No quality baseline or governance enforcement
- No programmatic access to the catalog from AI tools

## Plugins

This repository contains three complementary plugins that address the full API lifecycle:

```
Cognitiveapiupdater/
├── api-discovery-plugin/        # Plugin 1: Find and classify APIs
├── api-quality-plugin/          # Plugin 2: Audit, lint, and enforce standards
├── api-catalog-mcp-server/      # Plugin 3: MCP server for catalog access
└── README.md
```

### 1. API Discovery & Classification Plugin

**Purpose:** Discover what APIs exist across your organization and build a complete inventory.

| Capability | Description |
|------------|-------------|
| Multi-source discovery | Catalogs, Git repos, access logs, network scanning |
| Type classification | REST, GraphQL, SOAP, gRPC detection with confidence scoring |
| Documentation detection | OpenAPI/Swagger, WSDL, GraphQL schema |
| Tech fingerprinting | Language, framework, server, cloud provider identification |
| Ownership discovery | OpenAPI contacts, CODEOWNERS, CMDB, URL pattern inference |
| Criticality scoring | Weighted scoring: volume, exposure, sensitivity, business impact |

**Components:**
- 1 command (`/discover-apis`)
- 5 agents (api-classifier, spec-detector, tech-analyzer, ownership-finder, criticality-scorer)
- 5 skills (api-pattern-recognition, openapi-detector, graphql-introspection, soap-wsdl-parser, framework-fingerprinting)
- 4 scripts (multi_source_scanner, active_probe, passive_discovery, inventory_generator)

```bash
# Example: discover APIs from a catalog CSV
/discover-apis --input apis.csv

# Example: multi-source discovery
/discover-apis --sources catalog,git,logs --git-org my-org --log-dir /var/log/nginx/
```

**Output:** `api_inventory.json`, `discovery_report.md`, `orphaned_apis.csv`, `undocumented_apis.csv`

[Full documentation](api-discovery-plugin/README.md)

---

### 2. API Quality & Governance Toolkit

**Purpose:** Audit API specs for quality, enforce organizational standards, and generate improvement roadmaps.

| Capability | Description |
|------------|-------------|
| OpenAPI linting | Validate specs against configurable rulesets |
| Naming convention checks | Enforce consistent path, parameter, and schema naming |
| Security audit | Detect missing auth, exposed PII, insecure schemes |
| Versioning analysis | Check versioning strategy consistency |
| Deprecation tracking | Find deprecated endpoints still in use |
| Breaking change detection | Compare spec versions for compatibility |
| Compliance scoring | Score APIs against governance policies (0-100) |
| Bulk remediation | Generate fix scripts for common issues |

**Components:**
- 2 commands (`/audit-api`, `/governance-report`)
- 6 skills (openapi-linter, naming-conventions, security-checker, versioning-analyzer, deprecation-tracker, breaking-change-detector)
- 3 scripts (spec_auditor, governance_scorer, remediation_generator)

```bash
# Audit a single API spec
/audit-api --spec openapi.yaml

# Audit all specs in inventory
/audit-api --inventory api_inventory.json

# Generate governance report
/governance-report --inventory api_inventory.json --policy corporate-policy.yaml
```

**Output:** `audit_results.json`, `governance_report.md`, `remediation_plan.md`, `fixes/` directory

[Full documentation](api-quality-plugin/README.md)

---

### 3. API Catalog MCP Server

**Purpose:** Expose API inventory data through an MCP (Model Context Protocol) server so Claude and other AI tools can query the catalog in real time.

| Capability | Description |
|------------|-------------|
| MCP protocol | Standard MCP server with tools + resources |
| Catalog queries | Search, filter, and retrieve API metadata |
| Inventory stats | Aggregated statistics and dashboards |
| Ownership lookups | Find APIs by squad, department, or domain |
| Health monitoring | Real-time API health status |
| Integration bridge | Connect Claude to live API infrastructure |

**Components:**
- 1 MCP server (`api_catalog_server.py`)
- 6 MCP tools (search_apis, get_api_details, list_by_owner, get_stats, check_health, find_undocumented)
- 3 MCP resources (catalog://inventory, catalog://stats, catalog://health)
- 1 config file (`mcp_config.json`)

```bash
# Start the MCP server
python api-catalog-mcp-server/server/api_catalog_server.py --inventory api_inventory.json

# Configure in Claude Code settings
# Add to .claude/settings.json:
{
  "mcpServers": {
    "api-catalog": {
      "command": "python",
      "args": ["api-catalog-mcp-server/server/api_catalog_server.py", "--inventory", "api_inventory.json"]
    }
  }
}
```

**MCP tools available to Claude:**
- `search_apis(query, type, status)` - Search the API catalog
- `get_api_details(api_id)` - Get full details for a specific API
- `list_by_owner(squad)` - List all APIs owned by a squad
- `get_stats()` - Get catalog summary statistics
- `check_health(api_id)` - Check API health status
- `find_undocumented()` - List APIs missing documentation

[Full documentation](api-catalog-mcp-server/README.md)

---

## Workflow

The three plugins work together in sequence:

```
Step 1: DISCOVER                Step 2: AUDIT                  Step 3: SERVE
┌─────────────────────┐        ┌─────────────────────┐        ┌─────────────────────┐
│ api-discovery-plugin│───────>│  api-quality-plugin  │───────>│ api-catalog-mcp     │
│                     │        │                      │        │                     │
│ - Scan sources      │ JSON   │ - Lint specs         │ JSON   │ - MCP server        │
│ - Classify APIs     │ ────>  │ - Check security     │ ────>  │ - Query catalog     │
│ - Build inventory   │        │ - Score governance   │        │ - Live health       │
│ - Score criticality │        │ - Plan remediation   │        │ - AI-accessible     │
└─────────────────────┘        └─────────────────────┘        └─────────────────────┘
     api_inventory.json             audit_results.json           MCP tools/resources
```

1. **Discover** all APIs and generate `api_inventory.json`
2. **Audit** inventory for quality and governance compliance
3. **Serve** the enriched catalog via MCP for real-time AI access

## Getting Started

### Prerequisites

- Python 3.9+
- Claude Code CLI

### Installation

```bash
git clone https://github.com/edwardmonteiro/Cognitiveapiupdater.git
cd Cognitiveapiupdater

# Install dependencies for all plugins
pip install -r api-discovery-plugin/requirements.txt
pip install -r api-quality-plugin/requirements.txt
pip install -r api-catalog-mcp-server/requirements.txt
```

### Quick Start

```bash
# 1. Discover APIs from a CSV
cd api-discovery-plugin
python scripts/multi_source_scanner.py --sources catalog --input sample_apis.csv --output output/raw_apis.json
python scripts/active_probe.py --urls-file output/raw_apis.json --output output/probe_results.json
python scripts/inventory_generator.py --raw-apis output/raw_apis.json --probe-results output/probe_results.json --output-dir output/

# 2. Audit the discovered APIs
cd ../api-quality-plugin
python scripts/spec_auditor.py --inventory ../api-discovery-plugin/output/api_inventory.json --output-dir output/

# 3. Start the MCP server
cd ../api-catalog-mcp-server
python server/api_catalog_server.py --inventory ../api-discovery-plugin/output/api_inventory.json
```

## Repository Structure

```
Cognitiveapiupdater/
│
├── api-discovery-plugin/                  # Plugin 1: Discovery & Classification
│   ├── .claude-plugin/plugin.json
│   ├── commands/discover-apis.md
│   ├── agents/
│   │   ├── api-classifier/
│   │   ├── spec-detector/
│   │   ├── tech-analyzer/
│   │   ├── ownership-finder/
│   │   └── criticality-scorer/
│   ├── skills/
│   │   ├── api-pattern-recognition/
│   │   ├── openapi-detector/
│   │   ├── graphql-introspection/
│   │   ├── soap-wsdl-parser/
│   │   └── framework-fingerprinting/
│   ├── scripts/
│   │   ├── multi_source_scanner.py
│   │   ├── active_probe.py
│   │   ├── passive_discovery.py
│   │   └── inventory_generator.py
│   ├── requirements.txt
│   └── README.md
│
├── api-quality-plugin/                    # Plugin 2: Quality & Governance
│   ├── .claude-plugin/plugin.json
│   ├── commands/
│   │   ├── audit-api.md
│   │   └── governance-report.md
│   ├── skills/
│   │   ├── openapi-linter/
│   │   ├── naming-conventions/
│   │   ├── security-checker/
│   │   ├── versioning-analyzer/
│   │   ├── deprecation-tracker/
│   │   └── breaking-change-detector/
│   ├── scripts/
│   │   ├── spec_auditor.py
│   │   ├── governance_scorer.py
│   │   └── remediation_generator.py
│   ├── requirements.txt
│   └── README.md
│
├── api-catalog-mcp-server/                # Plugin 3: MCP Server
│   ├── server/
│   │   └── api_catalog_server.py
│   ├── mcp_config.json
│   ├── requirements.txt
│   └── README.md
│
├── LICENSE
└── README.md                              # This file
```

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

# API Catalog MCP Server

An MCP (Model Context Protocol) server that exposes API inventory data to Claude and other AI tools for real-time querying.

## What is MCP?

The Model Context Protocol (MCP) allows AI assistants like Claude to interact with external data sources and tools. This server implements MCP to provide Claude with access to your API catalog.

## Features

### Tools (Actions Claude can perform)

| Tool | Description | Parameters |
|------|-------------|------------|
| `search_apis` | Search catalog with filters | query, type, status, owner, criticality, limit |
| `get_api_details` | Get full API details | api_id |
| `list_by_owner` | List APIs by squad/team | owner |
| `get_stats` | Get catalog statistics | (none) |
| `check_health` | Check API health | api_id |
| `find_undocumented` | Find APIs without docs | limit |
| `find_orphaned` | Find APIs without owners | limit |

### Resources (Data Claude can read)

| URI | Description |
|-----|-------------|
| `catalog://inventory` | Complete API inventory |
| `catalog://stats` | Summary statistics |
| `catalog://health` | Health status overview |

### Prompts (Pre-built interactions)

| Prompt | Description |
|--------|-------------|
| `api_overview` | Generate API overview report |
| `squad_report` | Generate squad's API report |

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# The MCP SDK
pip install mcp
```

## Usage

### Start the Server

```bash
python server/api_catalog_server.py --inventory path/to/api_inventory.json
```

### Configure in Claude Code

Add to your `.claude/settings.json`:

```json
{
  "mcpServers": {
    "api-catalog": {
      "command": "python",
      "args": [
        "/path/to/api-catalog-mcp-server/server/api_catalog_server.py",
        "--inventory",
        "/path/to/api_inventory.json"
      ]
    }
  }
}
```

### Example Conversations with Claude

Once configured, you can ask Claude questions like:

**Search:**
> "Find all payment-related APIs"
> "Show me high-criticality REST APIs"
> "Which APIs does the Payments Squad own?"

**Details:**
> "Tell me about the payment-api-v2"
> "What technology stack does the account API use?"

**Analysis:**
> "Which APIs are missing documentation?"
> "Find all orphaned APIs and suggest owners"
> "Generate a report for the Credit Squad"

**Statistics:**
> "How many APIs do we have?"
> "What percentage of APIs have documentation?"

## Example Tool Responses

### search_apis

```json
{
  "count": 3,
  "apis": [
    {
      "id": "payment-api-v2",
      "name": "Payment API",
      "url": "https://api.example.com/v2/payments",
      "type": "REST",
      "status": "active",
      "owner": "Payments Squad",
      "criticality": "high"
    }
  ]
}
```

### get_stats

```json
{
  "total_apis": 150,
  "last_updated": "2026-02-05T14:30:00Z",
  "by_type": {
    "REST": 120,
    "GraphQL": 20,
    "SOAP": 8,
    "gRPC": 2
  },
  "documentation": {
    "with_docs": 100,
    "without_docs": 50
  },
  "ownership": {
    "with_owner": 130,
    "orphaned": 20
  }
}
```

## Architecture

```
┌─────────────────────┐
│    Claude Code      │
│  (MCP Client)       │
└─────────┬───────────┘
          │ MCP Protocol (stdio)
          │
┌─────────▼───────────┐
│  API Catalog MCP    │
│      Server         │
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│  api_inventory.json │
│  (from discovery    │
│   plugin)           │
└─────────────────────┘
```

## Integration with Other Plugins

This server consumes data from the API Discovery Plugin:

```bash
# 1. Run discovery
cd ../api-discovery-plugin
python scripts/inventory_generator.py --output-dir output/

# 2. Start MCP server with inventory
cd ../api-catalog-mcp-server
python server/api_catalog_server.py --inventory ../api-discovery-plugin/output/api_inventory.json
```

## Development

### Testing Locally

```bash
# Run server in development mode
python server/api_catalog_server.py --inventory sample_inventory.json

# The server communicates via stdin/stdout (MCP protocol)
```

### Adding New Tools

Edit `api_catalog_server.py` and add to:
1. `list_tools()` - Define the tool schema
2. `call_tool()` - Implement the tool logic

### Adding New Resources

Edit `api_catalog_server.py` and add to:
1. `list_resources()` - Define the resource
2. `read_resource()` - Return the resource content

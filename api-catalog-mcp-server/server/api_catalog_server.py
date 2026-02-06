#!/usr/bin/env python3
"""
API Catalog MCP Server

Exposes API inventory data through the Model Context Protocol (MCP),
allowing Claude and other AI tools to query the catalog in real time.

Usage:
    python api_catalog_server.py --inventory api_inventory.json

The server implements:
- Tools: search_apis, get_api_details, list_by_owner, get_stats, check_health, find_undocumented
- Resources: catalog://inventory, catalog://stats, catalog://health
"""

import argparse
import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any, Optional

# MCP SDK imports (install via: pip install mcp)
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        Resource,
        ResourceContents,
        GetPromptResult,
        Prompt,
        PromptArgument,
        PromptMessage,
    )
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("MCP SDK not installed. Install with: pip install mcp", file=sys.stderr)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("api_catalog_mcp")


class APICatalog:
    """In-memory API catalog loaded from inventory JSON."""

    def __init__(self, inventory_path: str):
        self.inventory_path = inventory_path
        self.inventory: dict = {}
        self.apis: list[dict] = []
        self.apis_by_id: dict[str, dict] = {}
        self.load()

    def load(self):
        """Load inventory from JSON file."""
        try:
            with open(self.inventory_path, 'r', encoding='utf-8') as f:
                self.inventory = json.load(f)
            self.apis = self.inventory.get('apis', [])
            self.apis_by_id = {api['id']: api for api in self.apis}
            logger.info(f"Loaded {len(self.apis)} APIs from {self.inventory_path}")
        except Exception as e:
            logger.error(f"Failed to load inventory: {e}")
            self.inventory = {}
            self.apis = []
            self.apis_by_id = {}

    def reload(self):
        """Reload inventory from disk."""
        self.load()

    def search(
        self,
        query: Optional[str] = None,
        api_type: Optional[str] = None,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        criticality: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search APIs with filters."""
        results = []

        for api in self.apis:
            basic = api.get('basic_info', {})
            ownership = api.get('ownership', {})
            crit = api.get('criticality', {})

            # Apply filters
            if api_type and basic.get('type', '').lower() != api_type.lower():
                continue
            if status and basic.get('status', '').lower() != status.lower():
                continue
            if owner:
                squad = ownership.get('squad', '').lower()
                dept = ownership.get('department', '').lower()
                if owner.lower() not in squad and owner.lower() not in dept:
                    continue
            if criticality and crit.get('level', '').lower() != criticality.lower():
                continue

            # Text search
            if query:
                query_lower = query.lower()
                searchable = f"{api.get('id', '')} {basic.get('name', '')} {basic.get('url', '')} {' '.join(api.get('tags', []))}".lower()
                if query_lower not in searchable:
                    continue

            results.append(api)

            if len(results) >= limit:
                break

        return results

    def get_by_id(self, api_id: str) -> Optional[dict]:
        """Get API by ID."""
        return self.apis_by_id.get(api_id)

    def list_by_owner(self, owner: str) -> list[dict]:
        """List all APIs by owner/squad."""
        results = []
        owner_lower = owner.lower()
        for api in self.apis:
            ownership = api.get('ownership', {})
            squad = ownership.get('squad', '').lower()
            dept = ownership.get('department', '').lower()
            email = ownership.get('email', '').lower()
            if owner_lower in squad or owner_lower in dept or owner_lower in email:
                results.append(api)
        return results

    def get_stats(self) -> dict:
        """Get catalog statistics."""
        summary = self.inventory.get('summary', {})
        metadata = self.inventory.get('discovery_metadata', {})

        return {
            "total_apis": len(self.apis),
            "last_updated": metadata.get('timestamp', 'unknown'),
            "sources_used": metadata.get('sources_used', []),
            "by_type": summary.get('by_type', {}),
            "by_status": summary.get('by_status', {}),
            "by_criticality": summary.get('by_criticality', {}),
            "documentation": {
                "with_docs": summary.get('with_documentation', 0),
                "without_docs": summary.get('without_documentation', 0),
            },
            "ownership": {
                "with_owner": summary.get('with_owner', 0),
                "orphaned": summary.get('orphaned', 0),
            },
        }

    def find_undocumented(self) -> list[dict]:
        """Find APIs without documentation."""
        results = []
        for api in self.apis:
            doc = api.get('documentation', {})
            if not doc.get('has_openapi') and not doc.get('has_wsdl') and not doc.get('has_graphql_schema'):
                results.append(api)
        return results

    def find_orphaned(self) -> list[dict]:
        """Find APIs without owner."""
        results = []
        for api in self.apis:
            ownership = api.get('ownership', {})
            if not ownership.get('squad'):
                results.append(api)
        return results

    def check_health(self, api_id: str) -> dict:
        """Check health status of an API (simulated)."""
        api = self.get_by_id(api_id)
        if not api:
            return {"error": f"API {api_id} not found"}

        basic = api.get('basic_info', {})
        status = basic.get('status', 'unknown')

        # Simulated health check (in real implementation, would ping the API)
        return {
            "api_id": api_id,
            "api_name": basic.get('name', ''),
            "url": basic.get('url', ''),
            "catalog_status": status,
            "health": {
                "status": "healthy" if status == "active" else "unknown",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "note": "Simulated health check based on catalog status",
            },
        }


def create_server(catalog: APICatalog) -> Server:
    """Create and configure the MCP server."""
    server = Server("api-catalog")

    # =========================================================================
    # TOOLS
    # =========================================================================

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_apis",
                description="Search the API catalog. Filter by query text, type (REST/GraphQL/SOAP/gRPC), status (active/deprecated), owner (squad name), or criticality (high/medium/low).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Text to search in API name, URL, tags",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["REST", "GraphQL", "SOAP", "gRPC"],
                            "description": "Filter by API type",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["active", "deprecated", "unknown"],
                            "description": "Filter by status",
                        },
                        "owner": {
                            "type": "string",
                            "description": "Filter by squad/team name",
                        },
                        "criticality": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Filter by criticality level",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 20)",
                            "default": 20,
                        },
                    },
                },
            ),
            Tool(
                name="get_api_details",
                description="Get full details for a specific API by its ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "api_id": {
                            "type": "string",
                            "description": "The API identifier",
                        },
                    },
                    "required": ["api_id"],
                },
            ),
            Tool(
                name="list_by_owner",
                description="List all APIs owned by a specific squad or team.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "owner": {
                            "type": "string",
                            "description": "Squad or team name",
                        },
                    },
                    "required": ["owner"],
                },
            ),
            Tool(
                name="get_stats",
                description="Get summary statistics for the entire API catalog.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="check_health",
                description="Check the health status of a specific API.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "api_id": {
                            "type": "string",
                            "description": "The API identifier",
                        },
                    },
                    "required": ["api_id"],
                },
            ),
            Tool(
                name="find_undocumented",
                description="List all APIs that are missing documentation (no OpenAPI/WSDL/GraphQL schema).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 50)",
                            "default": 50,
                        },
                    },
                },
            ),
            Tool(
                name="find_orphaned",
                description="List all APIs without an identified owner.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 50)",
                            "default": 50,
                        },
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "search_apis":
            results = catalog.search(
                query=arguments.get("query"),
                api_type=arguments.get("type"),
                status=arguments.get("status"),
                owner=arguments.get("owner"),
                criticality=arguments.get("criticality"),
                limit=arguments.get("limit", 20),
            )
            return [TextContent(
                type="text",
                text=json.dumps({
                    "count": len(results),
                    "apis": [
                        {
                            "id": api["id"],
                            "name": api.get("basic_info", {}).get("name", ""),
                            "url": api.get("basic_info", {}).get("url", ""),
                            "type": api.get("basic_info", {}).get("type", ""),
                            "status": api.get("basic_info", {}).get("status", ""),
                            "owner": api.get("ownership", {}).get("squad", ""),
                            "criticality": api.get("criticality", {}).get("level", ""),
                        }
                        for api in results
                    ],
                }, indent=2),
            )]

        elif name == "get_api_details":
            api = catalog.get_by_id(arguments["api_id"])
            if api:
                return [TextContent(type="text", text=json.dumps(api, indent=2))]
            return [TextContent(type="text", text=json.dumps({"error": "API not found"}))]

        elif name == "list_by_owner":
            results = catalog.list_by_owner(arguments["owner"])
            return [TextContent(
                type="text",
                text=json.dumps({
                    "owner": arguments["owner"],
                    "count": len(results),
                    "apis": [
                        {
                            "id": api["id"],
                            "name": api.get("basic_info", {}).get("name", ""),
                            "type": api.get("basic_info", {}).get("type", ""),
                            "criticality": api.get("criticality", {}).get("level", ""),
                        }
                        for api in results
                    ],
                }, indent=2),
            )]

        elif name == "get_stats":
            stats = catalog.get_stats()
            return [TextContent(type="text", text=json.dumps(stats, indent=2))]

        elif name == "check_health":
            result = catalog.check_health(arguments["api_id"])
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "find_undocumented":
            limit = arguments.get("limit", 50)
            results = catalog.find_undocumented()[:limit]
            return [TextContent(
                type="text",
                text=json.dumps({
                    "count": len(results),
                    "total_undocumented": len(catalog.find_undocumented()),
                    "apis": [
                        {
                            "id": api["id"],
                            "name": api.get("basic_info", {}).get("name", ""),
                            "type": api.get("basic_info", {}).get("type", ""),
                            "owner": api.get("ownership", {}).get("squad", ""),
                        }
                        for api in results
                    ],
                }, indent=2),
            )]

        elif name == "find_orphaned":
            limit = arguments.get("limit", 50)
            results = catalog.find_orphaned()[:limit]
            return [TextContent(
                type="text",
                text=json.dumps({
                    "count": len(results),
                    "total_orphaned": len(catalog.find_orphaned()),
                    "apis": [
                        {
                            "id": api["id"],
                            "name": api.get("basic_info", {}).get("name", ""),
                            "type": api.get("basic_info", {}).get("type", ""),
                            "criticality": api.get("criticality", {}).get("level", ""),
                        }
                        for api in results
                    ],
                }, indent=2),
            )]

        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    # =========================================================================
    # RESOURCES
    # =========================================================================

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="catalog://inventory",
                name="API Inventory",
                description="Complete API inventory with all metadata",
                mimeType="application/json",
            ),
            Resource(
                uri="catalog://stats",
                name="Catalog Statistics",
                description="Summary statistics for the API catalog",
                mimeType="application/json",
            ),
            Resource(
                uri="catalog://health",
                name="Catalog Health Overview",
                description="Health status overview for all APIs",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> ResourceContents:
        if uri == "catalog://inventory":
            return ResourceContents(
                uri=uri,
                mimeType="application/json",
                text=json.dumps(catalog.inventory, indent=2),
            )
        elif uri == "catalog://stats":
            return ResourceContents(
                uri=uri,
                mimeType="application/json",
                text=json.dumps(catalog.get_stats(), indent=2),
            )
        elif uri == "catalog://health":
            health_summary = {
                "total_apis": len(catalog.apis),
                "by_status": {},
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
            for api in catalog.apis:
                status = api.get("basic_info", {}).get("status", "unknown")
                health_summary["by_status"][status] = health_summary["by_status"].get(status, 0) + 1
            return ResourceContents(
                uri=uri,
                mimeType="application/json",
                text=json.dumps(health_summary, indent=2),
            )

        raise ValueError(f"Unknown resource: {uri}")

    # =========================================================================
    # PROMPTS
    # =========================================================================

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="api_overview",
                description="Generate an overview of a specific API",
                arguments=[
                    PromptArgument(
                        name="api_id",
                        description="The API identifier",
                        required=True,
                    ),
                ],
            ),
            Prompt(
                name="squad_report",
                description="Generate a report of all APIs owned by a squad",
                arguments=[
                    PromptArgument(
                        name="squad_name",
                        description="The squad/team name",
                        required=True,
                    ),
                ],
            ),
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict) -> GetPromptResult:
        if name == "api_overview":
            api = catalog.get_by_id(arguments["api_id"])
            if not api:
                return GetPromptResult(
                    description="API not found",
                    messages=[
                        PromptMessage(role="user", content=TextContent(
                            type="text",
                            text=f"API with ID '{arguments['api_id']}' was not found in the catalog.",
                        )),
                    ],
                )
            return GetPromptResult(
                description=f"Overview of {api.get('basic_info', {}).get('name', 'Unknown API')}",
                messages=[
                    PromptMessage(role="user", content=TextContent(
                        type="text",
                        text=f"Please provide an overview of this API:\n\n```json\n{json.dumps(api, indent=2)}\n```\n\nInclude: purpose, technology stack, ownership, criticality, and any issues or recommendations.",
                    )),
                ],
            )

        elif name == "squad_report":
            apis = catalog.list_by_owner(arguments["squad_name"])
            return GetPromptResult(
                description=f"API report for {arguments['squad_name']}",
                messages=[
                    PromptMessage(role="user", content=TextContent(
                        type="text",
                        text=f"Generate a report for the {arguments['squad_name']} squad.\n\nThey own {len(apis)} APIs:\n\n```json\n{json.dumps([{'id': a['id'], 'name': a.get('basic_info', {}).get('name', ''), 'criticality': a.get('criticality', {}).get('level', '')} for a in apis], indent=2)}\n```\n\nInclude: summary, high-criticality APIs that need attention, documentation gaps, and recommendations.",
                    )),
                ],
            )

        raise ValueError(f"Unknown prompt: {name}")

    return server


async def main():
    parser = argparse.ArgumentParser(description="API Catalog MCP Server")
    parser.add_argument("--inventory", required=True, help="Path to API inventory JSON")
    args = parser.parse_args()

    if not HAS_MCP:
        print("Error: MCP SDK not installed. Run: pip install mcp")
        sys.exit(1)

    catalog = APICatalog(args.inventory)
    server = create_server(catalog)

    logger.info("Starting API Catalog MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

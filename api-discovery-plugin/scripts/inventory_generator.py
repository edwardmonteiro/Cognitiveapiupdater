#!/usr/bin/env python3
"""
API Inventory Generator

Consolidates results from all discovery phases into:
- api_inventory.json: Complete API inventory
- discovery_report.md: Executive summary report
- orphaned_apis.csv: APIs without owners
- undocumented_apis.csv: APIs without documentation

Usage:
    python inventory_generator.py \
        --raw-apis output/raw_apis.json \
        --probe-results output/probe_results.json \
        --passive-results output/passive_apis.json \
        --output-dir output/
"""

import argparse
import csv
import json
import logging
import os
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("inventory_generator")


@dataclass
class APIEntry:
    """Complete API entry for the inventory."""

    id: str
    discovery_source: str = ""
    name: str = ""
    url: str = ""
    api_type: str = "unknown"
    status: str = "unknown"
    documentation: dict = field(default_factory=dict)
    technology: dict = field(default_factory=dict)
    ownership: dict = field(default_factory=dict)
    criticality: dict = field(default_factory=dict)
    authentication: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class CriticalityCalculator:
    """Calculates API criticality score."""

    # Keyword patterns for domain classification
    HIGH_IMPACT_KEYWORDS = [
        "payment", "pagamento", "pix", "transfer", "transferencia",
        "account", "conta", "credit", "credito", "debit", "debito",
        "auth", "login", "oauth", "token", "identity",
        "open-banking", "openbanking",
    ]

    MEDIUM_IMPACT_KEYWORDS = [
        "backoffice", "admin", "management", "report",
        "notification", "email", "sms", "customer", "cliente",
        "kyc", "compliance", "risk",
    ]

    LOW_IMPACT_KEYWORDS = [
        "analytics", "metrics", "logging", "health", "status",
        "docs", "documentation", "sandbox", "test", "mock",
        "experiment", "beta", "deprecated",
    ]

    def calculate(self, api: APIEntry) -> dict:
        """Calculate criticality score for an API."""
        volume_score = self._volume_score(api)
        exposure_score = self._exposure_score(api)
        sensitivity_score = self._sensitivity_score(api)
        impact_score = self._business_impact_score(api)

        total = (
            volume_score * 0.30
            + exposure_score * 0.25
            + sensitivity_score * 0.25
            + impact_score * 0.20
        )

        score = round(total * 100)
        level = self._score_to_level(score)
        reasons = self._explain_score(api, volume_score, exposure_score, sensitivity_score, impact_score)

        return {
            "level": level,
            "score": score,
            "components": {
                "volume": round(volume_score * 100),
                "external_exposure": round(exposure_score * 100),
                "data_sensitivity": round(sensitivity_score * 100),
                "business_impact": round(impact_score * 100),
            },
            "reasons": reasons,
        }

    def _volume_score(self, api: APIEntry) -> float:
        """Score based on request volume."""
        volume = api.metadata.get("request_volume", 0)
        vol_cat = api.metadata.get("volume_category", "")

        if vol_cat == "very_high" or volume > 100000:
            return 1.0
        elif vol_cat == "high" or volume > 10000:
            return 0.8
        elif vol_cat == "medium" or volume > 1000:
            return 0.5
        elif vol_cat == "low" or volume > 0:
            return 0.2
        return 0.3  # Unknown volume gets medium-low

    def _exposure_score(self, api: APIEntry) -> float:
        """Score based on external exposure."""
        url = (api.url or "").lower()
        name = (api.name or "").lower()
        tags = [t.lower() for t in api.tags]

        if any(kw in url or kw in name or kw in tags for kw in ["open-banking", "external", "public"]):
            return 1.0
        if any(kw in url for kw in ["api.itau.com", "api.example.com"]):
            return 0.8
        if any(kw in url for kw in ["internal", "private", "10.", "192.168"]):
            return 0.2
        return 0.5

    def _sensitivity_score(self, api: APIEntry) -> float:
        """Score based on data sensitivity."""
        text = f"{api.name} {api.url} {' '.join(api.tags)}".lower()

        pii_keywords = ["customer", "cliente", "user", "usuario", "personal", "cpf", "cnpj"]
        pci_keywords = ["payment", "card", "cartao", "credit", "credito", "account", "conta"]
        auth_keywords = ["auth", "token", "credential", "password", "secret"]

        if any(kw in text for kw in pci_keywords):
            return 1.0
        if any(kw in text for kw in auth_keywords):
            return 0.9
        if any(kw in text for kw in pii_keywords):
            return 0.7
        return 0.3

    def _business_impact_score(self, api: APIEntry) -> float:
        """Score based on business impact classification."""
        text = f"{api.name} {api.url} {' '.join(api.tags)}".lower()

        if any(kw in text for kw in self.HIGH_IMPACT_KEYWORDS):
            return 1.0
        if any(kw in text for kw in self.MEDIUM_IMPACT_KEYWORDS):
            return 0.5
        if any(kw in text for kw in self.LOW_IMPACT_KEYWORDS):
            return 0.2
        return 0.4

    def _score_to_level(self, score: int) -> str:
        """Convert numeric score to level."""
        if score >= 70:
            return "high"
        elif score >= 40:
            return "medium"
        return "low"

    def _explain_score(
        self, api: APIEntry, volume: float, exposure: float, sensitivity: float, impact: float
    ) -> list[str]:
        """Generate human-readable explanations for the score."""
        reasons = []
        text = f"{api.name} {api.url} {' '.join(api.tags)}".lower()

        if impact >= 0.8:
            reasons.append("Core banking API")
        if exposure >= 0.8:
            reasons.append("External exposure (potential Open Banking)")
        if sensitivity >= 0.8:
            reasons.append("Processes sensitive financial/personal data")
        if volume >= 0.8:
            vol = api.metadata.get("request_volume", "high")
            reasons.append(f"High request volume ({vol})")
        if "deprecated" in text:
            reasons.append("Deprecated API (still receiving traffic)")
        if not api.ownership.get("squad"):
            reasons.append("No ownership identified (orphaned)")

        if not reasons:
            reasons.append("Standard internal API")

        return reasons


class OwnershipInferrer:
    """Infers API ownership from various signals."""

    URL_PATTERNS = {
        "payment": {"squad": "Payments Squad", "department": "Core Banking"},
        "pagamento": {"squad": "Payments Squad", "department": "Core Banking"},
        "pix": {"squad": "Payments Squad", "department": "Core Banking"},
        "transfer": {"squad": "Transfers Squad", "department": "Core Banking"},
        "account": {"squad": "Accounts Squad", "department": "Core Banking"},
        "conta": {"squad": "Accounts Squad", "department": "Core Banking"},
        "credit": {"squad": "Credit Squad", "department": "Lending"},
        "credito": {"squad": "Credit Squad", "department": "Lending"},
        "card": {"squad": "Cards Squad", "department": "Cards"},
        "cartao": {"squad": "Cards Squad", "department": "Cards"},
        "auth": {"squad": "Identity Squad", "department": "Security"},
        "identity": {"squad": "Identity Squad", "department": "Security"},
        "notification": {"squad": "Notifications Squad", "department": "Channels"},
        "customer": {"squad": "CRM Squad", "department": "Customer Experience"},
        "kyc": {"squad": "Compliance Squad", "department": "Risk & Compliance"},
        "compliance": {"squad": "Compliance Squad", "department": "Risk & Compliance"},
        "analytics": {"squad": "Data Squad", "department": "Data & Analytics"},
        "report": {"squad": "Reporting Squad", "department": "Data & Analytics"},
    }

    def infer(self, api: APIEntry) -> dict:
        """Infer ownership for an API."""
        # Priority 1: Already have ownership from spec/catalog
        if api.ownership.get("squad"):
            return api.ownership

        # Priority 2: Metadata from discovery
        if api.metadata.get("owner") or api.metadata.get("squad"):
            return {
                "squad": api.metadata.get("squad", api.metadata.get("owner", "")),
                "email": api.metadata.get("email", ""),
                "department": api.metadata.get("department", ""),
                "source": "metadata",
            }

        # Priority 3: URL pattern inference
        text = f"{api.name} {api.url}".lower()
        for keyword, owner_info in self.URL_PATTERNS.items():
            if keyword in text:
                return {
                    "squad": owner_info["squad"],
                    "department": owner_info["department"],
                    "email": "",
                    "source": "url_pattern_inference",
                }

        return {"squad": "", "department": "", "email": "", "source": "not_found"}


class InventoryGenerator:
    """Generates the final API inventory and reports."""

    def __init__(self):
        self.criticality_calc = CriticalityCalculator()
        self.ownership_inferrer = OwnershipInferrer()
        self.logger = logging.getLogger("inventory_generator")

    def generate(
        self,
        raw_apis_file: Optional[str] = None,
        probe_results_file: Optional[str] = None,
        passive_results_file: Optional[str] = None,
        output_dir: str = "output",
    ) -> dict:
        """Generate the complete API inventory."""
        raw_apis = self._load_json(raw_apis_file) if raw_apis_file else {}
        probe_results = self._load_json(probe_results_file) if probe_results_file else {}
        passive_results = self._load_json(passive_results_file) if passive_results_file else {}

        # Merge all sources into APIEntry objects
        entries = self._merge_sources(raw_apis, probe_results, passive_results)

        # Enrich each entry
        for entry in entries:
            entry.ownership = self.ownership_inferrer.infer(entry)
            entry.criticality = self.criticality_calc.calculate(entry)
            entry.tags = self._generate_tags(entry)
            entry.status = self._infer_status(entry)

        # Build inventory
        inventory = self._build_inventory(entries)

        # Save all outputs
        os.makedirs(output_dir, exist_ok=True)
        self._save_inventory(inventory, os.path.join(output_dir, "api_inventory.json"))
        self._save_report(inventory, os.path.join(output_dir, "discovery_report.md"))
        self._save_orphaned_csv(entries, os.path.join(output_dir, "orphaned_apis.csv"))
        self._save_undocumented_csv(entries, os.path.join(output_dir, "undocumented_apis.csv"))

        return inventory

    def _load_json(self, filepath: str) -> dict:
        """Load a JSON file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"File not found: {filepath}")
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {filepath}: {e}")
            return {}

    def _merge_sources(self, raw: dict, probe: dict, passive: dict) -> list[APIEntry]:
        """Merge APIs from all sources into unified entries."""
        entries_map: dict[str, APIEntry] = {}

        # Process raw discovery results
        for api_data in raw.get("apis", []):
            url = api_data.get("url", "")
            key = self._normalize_key(url)
            if not key:
                continue

            entry = entries_map.get(key) or APIEntry(id=self._generate_id(url, api_data.get("name", "")))
            entry.url = url
            entry.name = api_data.get("name", "") or entry.name
            entry.discovery_source = api_data.get("source", "catalog")
            entry.metadata.update(api_data.get("metadata", {}))
            entries_map[key] = entry

        # Process probe results
        for result in probe.get("results", []):
            url = result.get("url", "")
            key = self._normalize_key(url)
            if not key:
                continue

            entry = entries_map.get(key) or APIEntry(id=self._generate_id(url))
            entry.url = url or entry.url
            entry.api_type = result.get("api_type", "unknown") if result.get("api_type") != "unknown" else entry.api_type
            entry.technology = result.get("technology", {}) or entry.technology
            entry.documentation = result.get("documentation", {}) or entry.documentation
            entry.metadata["reachable"] = result.get("reachable", False)
            entry.metadata["status_code"] = result.get("status_code", 0)
            entry.metadata["api_type_confidence"] = result.get("api_type_confidence", 0)
            entries_map[key] = entry

        # Process passive discovery results
        for api_data in passive.get("apis", []):
            url = api_data.get("url", "")
            key = self._normalize_key(url)
            if not key:
                continue

            entry = entries_map.get(key) or APIEntry(id=self._generate_id(url, api_data.get("name", "")))
            entry.url = url or entry.url
            entry.name = api_data.get("name", "") or entry.name
            if not entry.discovery_source:
                entry.discovery_source = "logs"
            entry.metadata["request_volume"] = api_data.get("request_volume", 0)
            entry.metadata["volume_category"] = api_data.get("volume_category", "")
            entry.metadata["unique_clients"] = api_data.get("unique_clients", 0)
            entry.metadata["error_rate"] = api_data.get("error_rate", 0)
            entry.metadata["methods_used"] = api_data.get("methods_used", [])
            entries_map[key] = entry

        return list(entries_map.values())

    def _normalize_key(self, url: str) -> str:
        """Normalize URL to use as dedup key."""
        url = url.lower().rstrip("/")
        url = url.replace("http://", "").replace("https://", "")
        # Remove port numbers
        import re
        url = re.sub(r":\d+", "", url)
        return url

    def _generate_id(self, url: str, name: str = "") -> str:
        """Generate a unique ID for an API entry."""
        import re
        base = name or url
        base = base.lower()
        base = re.sub(r"https?://", "", base)
        base = re.sub(r"[^a-z0-9]+", "-", base)
        base = base.strip("-")
        return base[:60] if base else "unknown"

    def _infer_status(self, api: APIEntry) -> str:
        """Infer API status."""
        text = f"{api.name} {api.url} {' '.join(api.tags)}".lower()

        if "deprecated" in text or "legacy" in text:
            return "deprecated"
        if api.metadata.get("reachable") is True:
            return "active"
        if api.metadata.get("reachable") is False:
            return "unreachable"
        if api.metadata.get("request_volume", 0) > 0:
            return "active"
        return "unknown"

    def _generate_tags(self, api: APIEntry) -> list[str]:
        """Generate tags for an API."""
        tags = set()
        text = f"{api.name} {api.url}".lower()

        tag_keywords = {
            "payment": "payment", "pagamento": "payment", "pix": "pix",
            "transfer": "transfer", "account": "account", "conta": "account",
            "credit": "credit", "card": "card", "auth": "authentication",
            "notification": "notification", "customer": "customer",
            "analytics": "analytics", "report": "reporting",
            "graphql": "graphql", "grpc": "grpc", "soap": "soap",
            "open-banking": "open-banking", "openbanking": "open-banking",
        }

        for keyword, tag in tag_keywords.items():
            if keyword in text:
                tags.add(tag)

        if api.api_type:
            tags.add(api.api_type.lower())

        return sorted(tags)

    def _build_inventory(self, entries: list[APIEntry]) -> dict:
        """Build the complete inventory JSON structure."""
        type_counts = Counter(e.api_type for e in entries)
        status_counts = Counter(e.status for e in entries)
        crit_counts = Counter(e.criticality.get("level", "unknown") for e in entries)

        with_docs = sum(1 for e in entries if e.documentation.get("has_openapi") or e.documentation.get("has_wsdl") or e.documentation.get("has_graphql_schema"))
        without_docs = len(entries) - with_docs

        with_owner = sum(1 for e in entries if e.ownership.get("squad"))
        orphaned = len(entries) - with_owner

        sources_used = sorted(set(e.discovery_source for e in entries if e.discovery_source))

        inventory = {
            "discovery_metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_apis_discovered": len(entries),
                "sources_used": sources_used,
            },
            "summary": {
                "by_type": dict(type_counts),
                "by_status": dict(status_counts),
                "by_criticality": dict(crit_counts),
                "with_documentation": with_docs,
                "without_documentation": without_docs,
                "with_owner": with_owner,
                "orphaned": orphaned,
            },
            "apis": [],
        }

        for entry in entries:
            api_obj = {
                "id": entry.id,
                "discovery_source": entry.discovery_source,
                "basic_info": {
                    "name": entry.name,
                    "url": entry.url,
                    "type": entry.api_type,
                    "status": entry.status,
                },
                "documentation": entry.documentation,
                "technology": entry.technology,
                "ownership": entry.ownership,
                "criticality": entry.criticality,
                "authentication": entry.authentication,
                "tags": entry.tags,
            }
            inventory["apis"].append(api_obj)

        return inventory

    def _save_inventory(self, inventory: dict, filepath: str):
        """Save the inventory JSON."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(inventory, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Inventory saved to {filepath}")

    def _save_report(self, inventory: dict, filepath: str):
        """Generate and save the discovery report in Markdown."""
        summary = inventory["summary"]
        total = inventory["discovery_metadata"]["total_apis_discovered"]
        timestamp = inventory["discovery_metadata"]["timestamp"]
        sources = ", ".join(inventory["discovery_metadata"]["sources_used"])

        type_dist = summary["by_type"]
        status_dist = summary["by_status"]
        crit_dist = summary["by_criticality"]

        def pct(n: int) -> str:
            return f"{(n / total * 100):.1f}%" if total > 0 else "0%"

        report = f"""# API Discovery Report
**Date:** {timestamp[:10]}
**Sources:** {sources}

## Executive Summary

A total of **{total} APIs** were discovered through analysis of {sources}.

## Distribution by Type

| Type | Count | Percentage |
|------|-------|------------|
"""
        for api_type, count in sorted(type_dist.items(), key=lambda x: x[1], reverse=True):
            report += f"| {api_type} | {count} | {pct(count)} |\n"

        report += f"""
## Status

| Status | Count | Percentage |
|--------|-------|------------|
"""
        for status, count in sorted(status_dist.items(), key=lambda x: x[1], reverse=True):
            report += f"| {status} | {count} | {pct(count)} |\n"

        report += f"""
## Documentation Coverage

- **With documentation:** {summary['with_documentation']} ({pct(summary['with_documentation'])})
- **Without documentation:** {summary['without_documentation']} ({pct(summary['without_documentation'])})

## Ownership

- **With owner identified:** {summary['with_owner']} ({pct(summary['with_owner'])})
- **Orphaned (no owner):** {summary['orphaned']} ({pct(summary['orphaned'])})

## Criticality

| Level | Count | Percentage |
|-------|-------|------------|
"""
        for level in ["high", "medium", "low", "unknown"]:
            count = crit_dist.get(level, 0)
            if count > 0:
                report += f"| {level.capitalize()} | {count} | {pct(count)} |\n"

        # Top issues
        orphaned_count = summary["orphaned"]
        undoc_count = summary["without_documentation"]
        soap_count = type_dist.get("SOAP", 0)
        unknown_count = status_dist.get("unknown", 0)

        report += f"""
## Key Issues

### 1. Orphaned APIs ({orphaned_count})
APIs without identified ownership pose maintenance and support risks.

**Action:** Establish an ownership assignment program.

### 2. Undocumented APIs ({undoc_count})
APIs without formal documentation (OpenAPI/WSDL) increase integration difficulty and support tickets.

**Action:** Mandate OpenAPI specifications for all APIs.

### 3. SOAP Legacy APIs ({soap_count})
SOAP APIs represent legacy technology that is harder to integrate and maintain.

**Action:** Create a migration roadmap from SOAP to REST.

### 4. Unknown Status APIs ({unknown_count})
APIs with unknown operational status need investigation.

**Action:** Verify reachability and current state of these APIs.

## Recommendations

1. **Governance:** Implement mandatory ownership policy for all APIs
2. **Documentation:** Require OpenAPI specification for new and existing APIs
3. **Modernization:** Plan 18-month roadmap to migrate SOAP to REST
4. **Security:** Audit all high-criticality APIs
5. **Monitoring:** Set up health checks for APIs with unknown status
6. **Decommission:** Review deprecated APIs still receiving traffic

## Next Steps

1. Review orphaned APIs and assign ownership
2. Create documentation program for undocumented APIs
3. Plan migration of legacy SOAP APIs to REST
4. Investigate APIs with unknown status
5. Run quality audit on high-criticality APIs
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
        self.logger.info(f"Report saved to {filepath}")

    def _save_orphaned_csv(self, entries: list[APIEntry], filepath: str):
        """Save orphaned APIs to CSV."""
        orphaned = [e for e in entries if not e.ownership.get("squad")]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "url", "type", "status", "criticality", "discovery_source"])
            for e in orphaned:
                writer.writerow([
                    e.id, e.name, e.url, e.api_type, e.status,
                    e.criticality.get("level", ""), e.discovery_source,
                ])
        self.logger.info(f"Orphaned APIs CSV saved to {filepath} ({len(orphaned)} entries)")

    def _save_undocumented_csv(self, entries: list[APIEntry], filepath: str):
        """Save undocumented APIs to CSV."""
        undocumented = [
            e for e in entries
            if not (e.documentation.get("has_openapi") or e.documentation.get("has_wsdl") or e.documentation.get("has_graphql_schema"))
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "url", "type", "status", "owner", "criticality", "discovery_source"])
            for e in undocumented:
                writer.writerow([
                    e.id, e.name, e.url, e.api_type, e.status,
                    e.ownership.get("squad", ""), e.criticality.get("level", ""),
                    e.discovery_source,
                ])
        self.logger.info(f"Undocumented APIs CSV saved to {filepath} ({len(undocumented)} entries)")

    def print_summary(self, inventory: dict):
        """Print a summary to the console."""
        summary = inventory["summary"]
        total = inventory["discovery_metadata"]["total_apis_discovered"]
        sources = inventory["discovery_metadata"]["sources_used"]

        def pct(n: int) -> str:
            return f"{(n / total * 100):.1f}%" if total > 0 else "0%"

        print("\n" + "=" * 60)
        print("  API Discovery Complete!")
        print("=" * 60)

        print(f"\n  Statistics:")
        print(f"  - Total APIs discovered: {total:,}")
        print(f"  - Sources used: {', '.join(sources)}")

        print(f"\n  Distribution:")
        for api_type, count in sorted(summary["by_type"].items(), key=lambda x: x[1], reverse=True):
            print(f"  - {api_type}: {count} ({pct(count)})")

        print(f"\n  Documentation:")
        print(f"  - With docs: {summary['with_documentation']} ({pct(summary['with_documentation'])})")
        print(f"  - Without docs: {summary['without_documentation']} ({pct(summary['without_documentation'])})")

        print(f"\n  Ownership:")
        print(f"  - With owner: {summary['with_owner']} ({pct(summary['with_owner'])})")
        print(f"  - Orphaned: {summary['orphaned']} ({pct(summary['orphaned'])})")

        print(f"\n  Criticality:")
        for level in ["high", "medium", "low"]:
            count = summary["by_criticality"].get(level, 0)
            print(f"  - {level.capitalize()}: {count} ({pct(count)})")

        print(f"\n  Issues:")
        print(f"  - {summary['orphaned']} orphaned APIs (no owner)")
        print(f"  - {summary['without_documentation']} undocumented APIs")
        soap = summary["by_type"].get("SOAP", 0)
        if soap:
            print(f"  - {soap} legacy SOAP APIs")
        unknown = summary["by_status"].get("unknown", 0)
        if unknown:
            print(f"  - {unknown} APIs with unknown status")

        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="API Inventory Generator")
    parser.add_argument("--raw-apis", help="Raw APIs JSON file (from multi_source_scanner)")
    parser.add_argument("--probe-results", help="Probe results JSON file (from active_probe)")
    parser.add_argument("--passive-results", help="Passive discovery results JSON file")
    parser.add_argument("--output-dir", default="output", help="Output directory")

    args = parser.parse_args()

    if not any([args.raw_apis, args.probe_results, args.passive_results]):
        print("Error: At least one input file required")
        print("  --raw-apis, --probe-results, or --passive-results")
        return

    generator = InventoryGenerator()
    inventory = generator.generate(
        raw_apis_file=args.raw_apis,
        probe_results_file=args.probe_results,
        passive_results_file=args.passive_results,
        output_dir=args.output_dir,
    )

    generator.print_summary(inventory)

    print(f"\n  Files generated:")
    print(f"  - {args.output_dir}/api_inventory.json")
    print(f"  - {args.output_dir}/discovery_report.md")
    print(f"  - {args.output_dir}/orphaned_apis.csv")
    print(f"  - {args.output_dir}/undocumented_apis.csv")


if __name__ == "__main__":
    main()

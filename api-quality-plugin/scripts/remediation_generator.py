#!/usr/bin/env python3
"""
Remediation Plan Generator

Generates prioritized remediation plans based on audit and governance results.

Usage:
    python remediation_generator.py \
        --audit audit_results.json \
        --governance governance_scorecard.json \
        --output-dir output/
"""

import argparse
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("remediation_generator")


@dataclass
class RemediationItem:
    api_id: str
    api_name: str
    category: str
    priority: str  # critical, high, medium, low
    issue: str
    action: str
    effort: str  # small, medium, large
    impact: str  # high, medium, low


class RemediationGenerator:
    """Generate prioritized remediation plans."""

    CATEGORY_PRIORITY = {
        "security": 1,
        "validity": 2,
        "documentation": 3,
        "ownership": 4,
        "naming": 5,
        "lifecycle": 6,
    }

    SEVERITY_PRIORITY = {
        "error": 1,
        "warning": 2,
        "info": 3,
    }

    ISSUE_ACTIONS = {
        "security-schemes-defined": {
            "action": "Add OAuth2 or API key security scheme to components.securitySchemes",
            "effort": "medium",
            "impact": "high",
        },
        "operation-security-required": {
            "action": "Add security requirement to each operation",
            "effort": "small",
            "impact": "high",
        },
        "https-required": {
            "action": "Update server URLs to use HTTPS",
            "effort": "small",
            "impact": "high",
        },
        "pii-documented": {
            "action": "Add x-pii: true annotation to PII fields",
            "effort": "small",
            "impact": "medium",
        },
        "operation-description": {
            "action": "Add description or summary to operation",
            "effort": "small",
            "impact": "medium",
        },
        "operation-id-required": {
            "action": "Add unique operationId to each operation",
            "effort": "small",
            "impact": "low",
        },
        "parameter-description": {
            "action": "Add descriptions to parameters",
            "effort": "small",
            "impact": "low",
        },
        "path-segment-kebab-case": {
            "action": "Rename path segments to use kebab-case",
            "effort": "large",
            "impact": "low",
        },
        "schema-name-pascal-case": {
            "action": "Rename schema to use PascalCase",
            "effort": "medium",
            "impact": "low",
        },
        "No owner/squad assigned": {
            "action": "Assign API to a squad and document in catalog",
            "effort": "small",
            "impact": "high",
        },
        "No API specification found": {
            "action": "Create OpenAPI 3.0 specification for this API",
            "effort": "large",
            "impact": "high",
        },
    }

    def generate_plan(
        self,
        audit_results: Optional[dict],
        governance_results: Optional[dict],
    ) -> dict:
        """Generate comprehensive remediation plan."""
        items = []

        # From audit results
        if audit_results:
            for result in audit_results.get("results", []):
                api_name = result.get("api_name", "Unknown")
                api_id = result.get("spec_path", "unknown")

                for issue in result.get("issues", []):
                    item = self._create_item_from_audit(api_id, api_name, issue)
                    if item:
                        items.append(item)

        # From governance results
        if governance_results:
            for api in governance_results.get("apis", []):
                api_id = api.get("api_id", "unknown")
                api_name = api.get("api_name", "Unknown")

                for dim_name, dim_data in api.get("dimensions", {}).items():
                    for issue_text in dim_data.get("issues", []):
                        item = self._create_item_from_governance(
                            api_id, api_name, dim_name, issue_text,
                            dim_data.get("recommendations", [])
                        )
                        if item:
                            items.append(item)

        # Deduplicate
        items = self._deduplicate(items)

        # Sort by priority
        items = self._prioritize(items)

        # Group by category
        by_category = defaultdict(list)
        for item in items:
            by_category[item.category].append(item)

        # Group by API
        by_api = defaultdict(list)
        for item in items:
            by_api[item.api_name].append(item)

        return {
            "summary": {
                "total_items": len(items),
                "by_priority": {
                    "critical": sum(1 for i in items if i.priority == "critical"),
                    "high": sum(1 for i in items if i.priority == "high"),
                    "medium": sum(1 for i in items if i.priority == "medium"),
                    "low": sum(1 for i in items if i.priority == "low"),
                },
                "by_category": {cat: len(its) for cat, its in by_category.items()},
                "by_effort": {
                    "small": sum(1 for i in items if i.effort == "small"),
                    "medium": sum(1 for i in items if i.effort == "medium"),
                    "large": sum(1 for i in items if i.effort == "large"),
                },
            },
            "items": [
                {
                    "api_id": i.api_id,
                    "api_name": i.api_name,
                    "category": i.category,
                    "priority": i.priority,
                    "issue": i.issue,
                    "action": i.action,
                    "effort": i.effort,
                    "impact": i.impact,
                }
                for i in items
            ],
            "by_category": {
                cat: [
                    {"api_name": i.api_name, "issue": i.issue, "action": i.action}
                    for i in its
                ]
                for cat, its in by_category.items()
            },
        }

    def _create_item_from_audit(
        self, api_id: str, api_name: str, issue: dict
    ) -> Optional[RemediationItem]:
        rule = issue.get("rule", "")
        severity = issue.get("severity", "info")
        category = issue.get("category", "other")
        message = issue.get("message", "")
        fix = issue.get("fix_suggestion", "")

        # Get action details from mapping or use suggestion
        action_info = self.ISSUE_ACTIONS.get(rule, {})
        action = action_info.get("action", fix or f"Fix: {message}")
        effort = action_info.get("effort", "medium")
        impact = action_info.get("impact", "medium")

        # Determine priority
        if severity == "error" and category == "security":
            priority = "critical"
        elif severity == "error":
            priority = "high"
        elif severity == "warning":
            priority = "medium"
        else:
            priority = "low"

        return RemediationItem(
            api_id=api_id,
            api_name=api_name,
            category=category,
            priority=priority,
            issue=message,
            action=action,
            effort=effort,
            impact=impact,
        )

    def _create_item_from_governance(
        self,
        api_id: str,
        api_name: str,
        dimension: str,
        issue_text: str,
        recommendations: list,
    ) -> Optional[RemediationItem]:
        # Get action from recommendations or mapping
        action_info = self.ISSUE_ACTIONS.get(issue_text, {})
        action = action_info.get("action", "")
        if not action and recommendations:
            action = recommendations[0]
        if not action:
            action = f"Address: {issue_text}"

        effort = action_info.get("effort", "medium")
        impact = action_info.get("impact", "medium")

        # Priority based on dimension
        if dimension == "security":
            priority = "high"
        elif dimension == "ownership":
            priority = "high"
        elif dimension == "documentation":
            priority = "medium"
        else:
            priority = "low"

        return RemediationItem(
            api_id=api_id,
            api_name=api_name,
            category=dimension,
            priority=priority,
            issue=issue_text,
            action=action,
            effort=effort,
            impact=impact,
        )

    def _deduplicate(self, items: list[RemediationItem]) -> list[RemediationItem]:
        seen = set()
        unique = []
        for item in items:
            key = (item.api_id, item.issue)
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    def _prioritize(self, items: list[RemediationItem]) -> list[RemediationItem]:
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        category_order = self.CATEGORY_PRIORITY

        return sorted(
            items,
            key=lambda x: (
                priority_order.get(x.priority, 9),
                category_order.get(x.category, 9),
                x.api_name,
            ),
        )


def generate_remediation_plan(
    audit_path: Optional[str],
    governance_path: Optional[str],
    output_dir: str,
):
    """Generate and save remediation plan."""
    os.makedirs(output_dir, exist_ok=True)

    audit = None
    governance = None

    if audit_path:
        with open(audit_path) as f:
            audit = json.load(f)

    if governance_path:
        with open(governance_path) as f:
            governance = json.load(f)

    generator = RemediationGenerator()
    plan = generator.generate_plan(audit, governance)

    # Save JSON
    json_path = os.path.join(output_dir, "remediation_plan.json")
    with open(json_path, "w") as f:
        json.dump(plan, f, indent=2)
    logger.info(f"Plan saved to {json_path}")

    # Generate markdown
    md_path = os.path.join(output_dir, "remediation_plan.md")
    with open(md_path, "w") as f:
        summary = plan["summary"]
        f.write("# API Remediation Plan\n\n")
        f.write("## Summary\n\n")
        f.write(f"- **Total items:** {summary['total_items']}\n\n")

        f.write("### By Priority\n\n")
        f.write("| Priority | Count |\n")
        f.write("|----------|-------|\n")
        for p in ["critical", "high", "medium", "low"]:
            f.write(f"| {p.title()} | {summary['by_priority'].get(p, 0)} |\n")

        f.write("\n### By Effort\n\n")
        f.write("| Effort | Count |\n")
        f.write("|--------|-------|\n")
        for e in ["small", "medium", "large"]:
            f.write(f"| {e.title()} | {summary['by_effort'].get(e, 0)} |\n")

        f.write("\n## Quick Wins (Small Effort, High Impact)\n\n")
        quick_wins = [
            i for i in plan["items"]
            if i["effort"] == "small" and i["impact"] == "high"
        ]
        if quick_wins:
            f.write("| API | Issue | Action |\n")
            f.write("|-----|-------|--------|\n")
            for item in quick_wins[:10]:
                f.write(f"| {item['api_name']} | {item['issue']} | {item['action']} |\n")
        else:
            f.write("No quick wins identified.\n")

        f.write("\n## Critical Items\n\n")
        critical = [i for i in plan["items"] if i["priority"] == "critical"]
        if critical:
            for item in critical:
                f.write(f"### {item['api_name']}\n\n")
                f.write(f"- **Issue:** {item['issue']}\n")
                f.write(f"- **Action:** {item['action']}\n")
                f.write(f"- **Effort:** {item['effort']}\n\n")
        else:
            f.write("No critical items.\n")

        f.write("\n## All Items by Category\n\n")
        for category, items in plan.get("by_category", {}).items():
            f.write(f"### {category.title()}\n\n")
            f.write("| API | Issue | Action |\n")
            f.write("|-----|-------|--------|\n")
            for item in items[:20]:
                f.write(f"| {item['api_name']} | {item['issue']} | {item['action']} |\n")
            if len(items) > 20:
                f.write(f"\n*...and {len(items) - 20} more items*\n")
            f.write("\n")

    logger.info(f"Markdown plan saved to {md_path}")

    # Print summary
    print(f"\nRemediation Plan Generated")
    print(f"  Total items: {summary['total_items']}")
    print(f"  Critical: {summary['by_priority'].get('critical', 0)}")
    print(f"  High: {summary['by_priority'].get('high', 0)}")
    print(f"  Quick wins: {len(quick_wins)}")


def main():
    parser = argparse.ArgumentParser(description="Remediation Plan Generator")
    parser.add_argument("--audit", help="Audit results JSON")
    parser.add_argument("--governance", help="Governance scorecard JSON")
    parser.add_argument("--output-dir", default="remediation-output")

    args = parser.parse_args()

    if not args.audit and not args.governance:
        print("Error: Provide --audit and/or --governance")
        return

    generate_remediation_plan(args.audit, args.governance, args.output_dir)


if __name__ == "__main__":
    main()

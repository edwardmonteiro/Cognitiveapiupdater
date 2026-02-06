#!/usr/bin/env python3
"""
API Governance Scorer

Calculates governance compliance scores across multiple dimensions.

Usage:
    python governance_scorer.py --inventory api_inventory.json --audit audit_results.json
"""

import argparse
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("governance_scorer")


@dataclass
class DimensionScore:
    name: str
    weight: float
    score: int  # 0-100
    max_score: int = 100
    issues: list = None
    recommendations: list = None

    def __post_init__(self):
        self.issues = self.issues or []
        self.recommendations = self.recommendations or []

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


class GovernanceScorer:
    """Calculate multi-dimensional governance scores."""

    DIMENSIONS = {
        "documentation": 0.25,  # OpenAPI completeness
        "security": 0.25,       # Auth, validation, PII
        "standards": 0.20,      # Naming, versioning, errors
        "ownership": 0.15,      # Owner assigned, contact info
        "lifecycle": 0.15,      # Status, deprecation, sunset
    }

    def score_api(self, api: dict, audit_result: Optional[dict] = None) -> dict:
        """Score a single API across all dimensions."""
        scores = {}

        scores["documentation"] = self._score_documentation(api, audit_result)
        scores["security"] = self._score_security(api, audit_result)
        scores["standards"] = self._score_standards(api, audit_result)
        scores["ownership"] = self._score_ownership(api)
        scores["lifecycle"] = self._score_lifecycle(api)

        total_weighted = sum(s.weighted_score for s in scores.values())
        overall_score = round(total_weighted)

        return {
            "api_id": api.get("id", "unknown"),
            "api_name": api.get("basic_info", {}).get("name", "Unknown"),
            "overall_score": overall_score,
            "grade": self._score_to_grade(overall_score),
            "dimensions": {
                name: {
                    "score": s.score,
                    "weight": s.weight,
                    "weighted_score": round(s.weighted_score, 1),
                    "issues": s.issues,
                    "recommendations": s.recommendations,
                }
                for name, s in scores.items()
            },
        }

    def _score_documentation(self, api: dict, audit: Optional[dict]) -> DimensionScore:
        score = 100
        issues = []
        recommendations = []

        doc = api.get("documentation", {})

        # Has spec?
        if not doc.get("has_openapi") and not doc.get("has_wsdl") and not doc.get("has_graphql_schema"):
            score -= 50
            issues.append("No API specification found")
            recommendations.append("Create OpenAPI specification for this API")

        # Endpoints documented?
        total_endpoints = doc.get("total_endpoints", 0)
        if total_endpoints == 0 and doc.get("has_openapi"):
            score -= 20
            issues.append("Spec has no endpoints defined")

        # From audit results
        if audit:
            doc_issues = [i for i in audit.get("issues", []) if i.get("category") == "documentation"]
            error_count = sum(1 for i in doc_issues if i.get("severity") == "error")
            warning_count = sum(1 for i in doc_issues if i.get("severity") == "warning")
            score -= error_count * 10
            score -= warning_count * 3
            if doc_issues:
                issues.append(f"{len(doc_issues)} documentation issues in spec")

        return DimensionScore(
            name="documentation",
            weight=self.DIMENSIONS["documentation"],
            score=max(0, score),
            issues=issues,
            recommendations=recommendations,
        )

    def _score_security(self, api: dict, audit: Optional[dict]) -> DimensionScore:
        score = 100
        issues = []
        recommendations = []

        auth = api.get("authentication", {})
        methods = auth.get("methods", [])

        if not methods:
            score -= 40
            issues.append("No authentication method defined")
            recommendations.append("Implement OAuth2 or API key authentication")
        elif "none" in methods:
            score -= 50
            issues.append("API allows unauthenticated access")

        # Check URL scheme
        url = api.get("basic_info", {}).get("url", "")
        if url.startswith("http://") and "localhost" not in url:
            score -= 30
            issues.append("API uses HTTP instead of HTTPS")
            recommendations.append("Enable HTTPS for all endpoints")

        # From audit
        if audit:
            sec_issues = [i for i in audit.get("issues", []) if i.get("category") == "security"]
            error_count = sum(1 for i in sec_issues if i.get("severity") == "error")
            warning_count = sum(1 for i in sec_issues if i.get("severity") == "warning")
            score -= error_count * 15
            score -= warning_count * 5
            if sec_issues:
                issues.append(f"{len(sec_issues)} security issues detected")

        return DimensionScore(
            name="security",
            weight=self.DIMENSIONS["security"],
            score=max(0, score),
            issues=issues,
            recommendations=recommendations,
        )

    def _score_standards(self, api: dict, audit: Optional[dict]) -> DimensionScore:
        score = 100
        issues = []
        recommendations = []

        # From audit - naming and validity
        if audit:
            std_issues = [
                i for i in audit.get("issues", [])
                if i.get("category") in ("naming", "validity")
            ]
            error_count = sum(1 for i in std_issues if i.get("severity") == "error")
            warning_count = sum(1 for i in std_issues if i.get("severity") == "warning")
            score -= error_count * 10
            score -= warning_count * 3
            if std_issues:
                issues.append(f"{len(std_issues)} standards violations")

        # Check versioning
        url = api.get("basic_info", {}).get("url", "")
        import re
        if not re.search(r'/v\d+', url):
            score -= 10
            issues.append("No version in URL path")
            recommendations.append("Use URL versioning (e.g., /v1/)")

        return DimensionScore(
            name="standards",
            weight=self.DIMENSIONS["standards"],
            score=max(0, score),
            issues=issues,
            recommendations=recommendations,
        )

    def _score_ownership(self, api: dict) -> DimensionScore:
        score = 100
        issues = []
        recommendations = []

        ownership = api.get("ownership", {})

        if not ownership.get("squad"):
            score -= 50
            issues.append("No owner/squad assigned")
            recommendations.append("Assign API ownership to a squad")

        if not ownership.get("email"):
            score -= 20
            issues.append("No contact email")
            recommendations.append("Add contact email to OpenAPI info.contact")

        if not ownership.get("department"):
            score -= 10
            issues.append("Department not identified")

        source = ownership.get("source", "")
        if source == "url_pattern_inference":
            score -= 10
            issues.append("Ownership inferred from URL pattern (not explicit)")
            recommendations.append("Document ownership explicitly in spec or catalog")

        return DimensionScore(
            name="ownership",
            weight=self.DIMENSIONS["ownership"],
            score=max(0, score),
            issues=issues,
            recommendations=recommendations,
        )

    def _score_lifecycle(self, api: dict) -> DimensionScore:
        score = 100
        issues = []
        recommendations = []

        basic = api.get("basic_info", {})
        status = basic.get("status", "unknown")

        if status == "unknown":
            score -= 30
            issues.append("API status is unknown")
            recommendations.append("Verify API status and update catalog")
        elif status == "deprecated":
            score -= 20
            issues.append("API is deprecated")
            recommendations.append("Plan migration to replacement API")
        elif status == "unreachable":
            score -= 50
            issues.append("API is unreachable")
            recommendations.append("Investigate connectivity or decommission")

        # Check for sunset dates on deprecated APIs
        if status == "deprecated":
            # Would check x-sunset-date if available
            pass

        return DimensionScore(
            name="lifecycle",
            weight=self.DIMENSIONS["lifecycle"],
            score=max(0, score),
            issues=issues,
            recommendations=recommendations,
        )

    def _score_to_grade(self, score: int) -> str:
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        return "F"


def generate_governance_report(
    inventory: dict,
    audit_results: Optional[dict],
    output_dir: str,
):
    """Generate governance scorecard and report."""
    os.makedirs(output_dir, exist_ok=True)
    scorer = GovernanceScorer()

    # Map audit results by API
    audit_by_api = {}
    if audit_results:
        for result in audit_results.get("results", []):
            api_name = result.get("api_name", "")
            if api_name:
                audit_by_api[api_name] = result

    # Score each API
    scored_apis = []
    for api in inventory.get("apis", []):
        api_name = api.get("basic_info", {}).get("name", "")
        audit = audit_by_api.get(api_name)
        scored = scorer.score_api(api, audit)
        scored_apis.append(scored)

    # Calculate fleet-level stats
    total = len(scored_apis)
    if total == 0:
        logger.warning("No APIs to score")
        return

    avg_score = round(sum(s["overall_score"] for s in scored_apis) / total, 1)
    by_grade = {}
    for s in scored_apis:
        grade = s["grade"]
        by_grade[grade] = by_grade.get(grade, 0) + 1

    # Dimension averages
    dim_avgs = {}
    for dim in GovernanceScorer.DIMENSIONS:
        dim_scores = [s["dimensions"][dim]["score"] for s in scored_apis]
        dim_avgs[dim] = round(sum(dim_scores) / len(dim_scores), 1)

    # Build output
    output = {
        "summary": {
            "total_apis": total,
            "average_score": avg_score,
            "average_grade": scorer._score_to_grade(int(avg_score)),
            "by_grade": by_grade,
            "dimension_averages": dim_avgs,
        },
        "apis": scored_apis,
    }

    # Save JSON
    json_path = os.path.join(output_dir, "governance_scorecard.json")
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2)
    logger.info(f"Scorecard saved to {json_path}")

    # Generate markdown report
    md_path = os.path.join(output_dir, "governance_report.md")
    with open(md_path, "w") as f:
        f.write("# API Governance Report\n\n")
        f.write("## Executive Summary\n\n")
        f.write(f"- **Total APIs:** {total}\n")
        f.write(f"- **Average Score:** {avg_score}/100 (Grade: {scorer._score_to_grade(int(avg_score))})\n\n")

        f.write("### Grade Distribution\n\n")
        f.write("| Grade | Count | Percentage |\n")
        f.write("|-------|-------|------------|\n")
        for grade in ["A", "B", "C", "D", "F"]:
            count = by_grade.get(grade, 0)
            pct = round(count / total * 100, 1) if total > 0 else 0
            f.write(f"| {grade} | {count} | {pct}% |\n")

        f.write("\n### Scores by Dimension\n\n")
        f.write("| Dimension | Average Score | Weight |\n")
        f.write("|-----------|---------------|--------|\n")
        for dim, weight in GovernanceScorer.DIMENSIONS.items():
            f.write(f"| {dim.title()} | {dim_avgs[dim]} | {int(weight*100)}% |\n")

        f.write("\n## APIs Needing Attention\n\n")
        low_scoring = [s for s in scored_apis if s["overall_score"] < 70]
        if low_scoring:
            f.write("| API | Score | Grade | Top Issues |\n")
            f.write("|-----|-------|-------|------------|\n")
            for api in sorted(low_scoring, key=lambda x: x["overall_score"]):
                all_issues = []
                for dim in api["dimensions"].values():
                    all_issues.extend(dim.get("issues", []))
                top_issues = "; ".join(all_issues[:3])
                f.write(f"| {api['api_name']} | {api['overall_score']} | {api['grade']} | {top_issues} |\n")
        else:
            f.write("All APIs have acceptable governance scores.\n")

    logger.info(f"Report saved to {md_path}")


def main():
    parser = argparse.ArgumentParser(description="API Governance Scorer")
    parser.add_argument("--inventory", required=True, help="API inventory JSON")
    parser.add_argument("--audit", help="Audit results JSON (optional)")
    parser.add_argument("--output-dir", default="governance-output")

    args = parser.parse_args()

    with open(args.inventory) as f:
        inventory = json.load(f)

    audit_results = None
    if args.audit:
        with open(args.audit) as f:
            audit_results = json.load(f)

    generate_governance_report(inventory, audit_results, args.output_dir)


if __name__ == "__main__":
    main()

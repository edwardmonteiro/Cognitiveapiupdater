#!/usr/bin/env python3
"""
OpenAPI Specification Auditor

Audits OpenAPI specs for quality, security, naming conventions, and compliance.

Usage:
    python spec_auditor.py --spec openapi.yaml
    python spec_auditor.py --inventory api_inventory.json --output-dir output/
"""

import argparse
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("spec_auditor")


@dataclass
class Issue:
    rule: str
    severity: str  # error, warning, info
    message: str
    path: str = ""
    line: int = 0
    fix_suggestion: str = ""
    category: str = ""


@dataclass
class AuditResult:
    spec_path: str
    api_name: str = ""
    api_version: str = ""
    passed: bool = True
    score: int = 100
    issues: list = field(default_factory=list)


class NamingChecker:
    """Check naming conventions."""

    @staticmethod
    def is_kebab_case(s: str) -> bool:
        return bool(re.match(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$', s))

    @staticmethod
    def is_camel_case(s: str) -> bool:
        return bool(re.match(r'^[a-z][a-zA-Z0-9]*$', s))

    @staticmethod
    def is_pascal_case(s: str) -> bool:
        return bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', s))

    def check_path(self, path: str) -> list[Issue]:
        issues = []
        segments = path.strip('/').split('/')
        for seg in segments:
            if seg.startswith('{') and seg.endswith('}'):
                param = seg[1:-1]
                if not self.is_camel_case(param):
                    issues.append(Issue(
                        rule="path-param-camel-case",
                        severity="warning",
                        message=f"Path parameter '{param}' should be camelCase",
                        path=f"paths.{path}",
                        category="naming"
                    ))
            elif not seg.startswith('v') and not self.is_kebab_case(seg) and seg:
                issues.append(Issue(
                    rule="path-segment-kebab-case",
                    severity="warning",
                    message=f"Path segment '{seg}' should be kebab-case",
                    path=f"paths.{path}",
                    category="naming"
                ))
        return issues

    def check_schema_name(self, name: str) -> Optional[Issue]:
        if not self.is_pascal_case(name):
            return Issue(
                rule="schema-name-pascal-case",
                severity="warning",
                message=f"Schema '{name}' should be PascalCase",
                path=f"components.schemas.{name}",
                category="naming"
            )
        return None

    def check_property_name(self, prop: str, schema_name: str) -> Optional[Issue]:
        if not self.is_camel_case(prop) and prop not in ('id', 'url', 'uri'):
            return Issue(
                rule="property-camel-case",
                severity="warning",
                message=f"Property '{prop}' in schema '{schema_name}' should be camelCase",
                path=f"components.schemas.{schema_name}.properties.{prop}",
                category="naming"
            )
        return None


class SecurityChecker:
    """Check security configuration."""

    PII_PATTERNS = [
        'cpf', 'cnpj', 'ssn', 'tax_id', 'taxId',
        'email', 'phone', 'mobile', 'address',
        'password', 'secret', 'token', 'credential',
        'card_number', 'cardNumber', 'cvv', 'pan',
        'first_name', 'firstName', 'last_name', 'lastName',
        'birth_date', 'birthDate', 'date_of_birth'
    ]

    def check_security_defined(self, spec: dict) -> list[Issue]:
        issues = []
        security_schemes = spec.get('components', {}).get('securitySchemes', {})
        if not security_schemes:
            issues.append(Issue(
                rule="security-schemes-defined",
                severity="error",
                message="No security schemes defined in components.securitySchemes",
                path="components.securitySchemes",
                category="security",
                fix_suggestion="Add OAuth2, Bearer, or API Key security scheme"
            ))
        return issues

    def check_operation_security(self, path: str, method: str, operation: dict) -> list[Issue]:
        issues = []
        if 'security' not in operation and method.lower() not in ('options', 'head'):
            issues.append(Issue(
                rule="operation-security-required",
                severity="error",
                message=f"Operation {method.upper()} {path} has no security requirement",
                path=f"paths.{path}.{method}",
                category="security",
                fix_suggestion="Add 'security' field with appropriate scheme"
            ))
        return issues

    def check_https(self, servers: list) -> list[Issue]:
        issues = []
        for i, server in enumerate(servers):
            url = server.get('url', '')
            if url.startswith('http://') and 'localhost' not in url and '127.0.0.1' not in url:
                issues.append(Issue(
                    rule="https-required",
                    severity="error",
                    message=f"Server URL '{url}' uses HTTP instead of HTTPS",
                    path=f"servers[{i}].url",
                    category="security"
                ))
        return issues

    def check_pii_fields(self, schema_name: str, properties: dict) -> list[Issue]:
        issues = []
        for prop_name in properties:
            for pattern in self.PII_PATTERNS:
                if pattern.lower() in prop_name.lower():
                    prop_def = properties[prop_name]
                    if not prop_def.get('x-pii') and not prop_def.get('description', '').lower().count('pii'):
                        issues.append(Issue(
                            rule="pii-documented",
                            severity="warning",
                            message=f"Field '{prop_name}' in '{schema_name}' appears to be PII but is not documented as such",
                            path=f"components.schemas.{schema_name}.properties.{prop_name}",
                            category="security",
                            fix_suggestion="Add 'x-pii: true' or document in description"
                        ))
                    break
        return issues


class DocumentationChecker:
    """Check documentation completeness."""

    def check_operation(self, path: str, method: str, operation: dict) -> list[Issue]:
        issues = []
        if not operation.get('description') and not operation.get('summary'):
            issues.append(Issue(
                rule="operation-description",
                severity="warning",
                message=f"Operation {method.upper()} {path} has no description or summary",
                path=f"paths.{path}.{method}",
                category="documentation"
            ))
        if not operation.get('operationId'):
            issues.append(Issue(
                rule="operation-id-required",
                severity="warning",
                message=f"Operation {method.upper()} {path} has no operationId",
                path=f"paths.{path}.{method}",
                category="documentation"
            ))
        return issues

    def check_parameters(self, path: str, method: str, parameters: list) -> list[Issue]:
        issues = []
        for i, param in enumerate(parameters):
            if not param.get('description'):
                issues.append(Issue(
                    rule="parameter-description",
                    severity="info",
                    message=f"Parameter '{param.get('name')}' in {method.upper()} {path} has no description",
                    path=f"paths.{path}.{method}.parameters[{i}]",
                    category="documentation"
                ))
        return issues

    def check_responses(self, path: str, method: str, responses: dict) -> list[Issue]:
        issues = []
        for code, response in responses.items():
            if not response.get('description'):
                issues.append(Issue(
                    rule="response-description",
                    severity="info",
                    message=f"Response {code} in {method.upper()} {path} has no description",
                    path=f"paths.{path}.{method}.responses.{code}",
                    category="documentation"
                ))

        # Check for error responses
        has_error = any(str(c).startswith(('4', '5')) for c in responses.keys())
        if not has_error and method.lower() in ('post', 'put', 'patch', 'delete'):
            issues.append(Issue(
                rule="error-responses-documented",
                severity="warning",
                message=f"Operation {method.upper()} {path} has no error responses (4xx, 5xx)",
                path=f"paths.{path}.{method}.responses",
                category="documentation"
            ))
        return issues


class SpecAuditor:
    """Main auditor class."""

    def __init__(self, ruleset: str = "standard"):
        self.ruleset = ruleset
        self.naming = NamingChecker()
        self.security = SecurityChecker()
        self.docs = DocumentationChecker()

    def load_spec(self, spec_path: str) -> Optional[dict]:
        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if spec_path.endswith(('.yaml', '.yml')):
                if not HAS_YAML:
                    logger.error("PyYAML not installed. Install with: pip install pyyaml")
                    return None
                return yaml.safe_load(content)
            else:
                return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load spec {spec_path}: {e}")
            return None

    def audit(self, spec_path: str) -> AuditResult:
        result = AuditResult(spec_path=spec_path)

        spec = self.load_spec(spec_path)
        if not spec:
            result.passed = False
            result.score = 0
            result.issues.append(Issue(
                rule="spec-parse-error",
                severity="error",
                message="Failed to parse specification file",
                category="validity"
            ))
            return result

        # Extract basic info
        info = spec.get('info', {})
        result.api_name = info.get('title', 'Unknown')
        result.api_version = info.get('version', '')

        # Run all checks
        result.issues.extend(self._check_structure(spec))
        result.issues.extend(self._check_paths(spec))
        result.issues.extend(self._check_schemas(spec))
        result.issues.extend(self.security.check_security_defined(spec))
        result.issues.extend(self.security.check_https(spec.get('servers', [])))

        # Calculate score
        result.score = self._calculate_score(result.issues)
        result.passed = not any(i.severity == 'error' for i in result.issues)

        return result

    def _check_structure(self, spec: dict) -> list[Issue]:
        issues = []
        if 'openapi' not in spec:
            issues.append(Issue(
                rule="openapi-version",
                severity="error",
                message="Missing 'openapi' version field",
                category="validity"
            ))
        if 'info' not in spec:
            issues.append(Issue(
                rule="info-required",
                severity="error",
                message="Missing 'info' object",
                category="validity"
            ))
        if 'paths' not in spec or not spec['paths']:
            issues.append(Issue(
                rule="paths-required",
                severity="error",
                message="Missing or empty 'paths' object",
                category="validity"
            ))
        return issues

    def _check_paths(self, spec: dict) -> list[Issue]:
        issues = []
        global_security = spec.get('security')

        for path, path_item in spec.get('paths', {}).items():
            issues.extend(self.naming.check_path(path))

            for method in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']:
                if method not in path_item:
                    continue
                operation = path_item[method]

                issues.extend(self.docs.check_operation(path, method, operation))
                issues.extend(self.docs.check_parameters(path, method, operation.get('parameters', [])))
                issues.extend(self.docs.check_responses(path, method, operation.get('responses', {})))

                if not global_security:
                    issues.extend(self.security.check_operation_security(path, method, operation))

        return issues

    def _check_schemas(self, spec: dict) -> list[Issue]:
        issues = []
        schemas = spec.get('components', {}).get('schemas', {})

        for name, schema in schemas.items():
            issue = self.naming.check_schema_name(name)
            if issue:
                issues.append(issue)

            properties = schema.get('properties', {})
            for prop_name in properties:
                issue = self.naming.check_property_name(prop_name, name)
                if issue:
                    issues.append(issue)

            issues.extend(self.security.check_pii_fields(name, properties))

        return issues

    def _calculate_score(self, issues: list[Issue]) -> int:
        score = 100
        for issue in issues:
            if issue.severity == 'error':
                score -= 15
            elif issue.severity == 'warning':
                score -= 5
            elif issue.severity == 'info':
                score -= 1
        return max(0, score)


def generate_report(results: list[AuditResult], output_dir: str):
    """Generate audit report files."""
    os.makedirs(output_dir, exist_ok=True)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    all_issues = [i for r in results for i in r.issues]
    by_severity = {
        'error': sum(1 for i in all_issues if i.severity == 'error'),
        'warning': sum(1 for i in all_issues if i.severity == 'warning'),
        'info': sum(1 for i in all_issues if i.severity == 'info')
    }

    summary = {
        "total_specs": total,
        "passed": passed,
        "failed": total - passed,
        "total_issues": len(all_issues),
        "by_severity": by_severity,
        "average_score": round(sum(r.score for r in results) / total, 1) if total > 0 else 0
    }

    # JSON output
    output = {
        "summary": summary,
        "results": [
            {
                "spec_path": r.spec_path,
                "api_name": r.api_name,
                "api_version": r.api_version,
                "passed": r.passed,
                "score": r.score,
                "issues": [
                    {
                        "rule": i.rule,
                        "severity": i.severity,
                        "message": i.message,
                        "path": i.path,
                        "category": i.category,
                        "fix_suggestion": i.fix_suggestion
                    }
                    for i in r.issues
                ]
            }
            for r in results
        ]
    }

    json_path = os.path.join(output_dir, "audit_results.json")
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2)
    logger.info(f"Results saved to {json_path}")

    # Markdown report
    md_path = os.path.join(output_dir, "audit_report.md")
    with open(md_path, 'w') as f:
        f.write("# API Audit Report\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- **Total specs audited:** {total}\n")
        f.write(f"- **Passed:** {passed}\n")
        f.write(f"- **Failed:** {total - passed}\n")
        f.write(f"- **Average score:** {summary['average_score']}\n")
        f.write(f"- **Total issues:** {len(all_issues)}\n")
        f.write(f"  - Errors: {by_severity['error']}\n")
        f.write(f"  - Warnings: {by_severity['warning']}\n")
        f.write(f"  - Info: {by_severity['info']}\n\n")

        f.write("## Results by API\n\n")
        for r in sorted(results, key=lambda x: x.score):
            status = "PASS" if r.passed else "FAIL"
            f.write(f"### {r.api_name} ({r.api_version})\n\n")
            f.write(f"- **Status:** {status}\n")
            f.write(f"- **Score:** {r.score}/100\n")
            f.write(f"- **File:** {r.spec_path}\n\n")

            if r.issues:
                f.write("| Severity | Rule | Message |\n")
                f.write("|----------|------|---------|n")
                for i in sorted(r.issues, key=lambda x: {'error': 0, 'warning': 1, 'info': 2}[x.severity]):
                    f.write(f"| {i.severity} | {i.rule} | {i.message} |\n")
                f.write("\n")

    logger.info(f"Report saved to {md_path}")


def main():
    parser = argparse.ArgumentParser(description="OpenAPI Specification Auditor")
    parser.add_argument("--spec", help="Path to single OpenAPI spec")
    parser.add_argument("--specs", help="Glob pattern for multiple specs")
    parser.add_argument("--inventory", help="Path to API inventory JSON")
    parser.add_argument("--ruleset", default="standard", choices=["minimal", "standard", "strict"])
    parser.add_argument("--output-dir", default="audit-output")

    args = parser.parse_args()

    auditor = SpecAuditor(ruleset=args.ruleset)
    results = []

    if args.spec:
        results.append(auditor.audit(args.spec))

    if args.specs:
        from glob import glob
        for spec_path in glob(args.specs):
            results.append(auditor.audit(spec_path))

    if args.inventory:
        with open(args.inventory) as f:
            inventory = json.load(f)
        for api in inventory.get('apis', []):
            doc = api.get('documentation', {})
            spec_url = doc.get('openapi_url') or doc.get('spec_path')
            if spec_url and os.path.exists(spec_url):
                results.append(auditor.audit(spec_url))

    if not results:
        print("No specs to audit. Provide --spec, --specs, or --inventory")
        return

    generate_report(results, args.output_dir)

    # Print summary
    passed = sum(1 for r in results if r.passed)
    print(f"\nAudit complete: {passed}/{len(results)} specs passed")
    print(f"Results saved to {args.output_dir}/")


if __name__ == "__main__":
    main()

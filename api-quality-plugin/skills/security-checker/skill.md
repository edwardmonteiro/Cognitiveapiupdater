# Security Checker Skill

## Purpose
Detects security vulnerabilities and misconfigurations in OpenAPI specifications.

## Security Rules

### Authentication & Authorization

| Rule ID | Severity | Description |
|---------|----------|-------------|
| `security-defined` | error | Security schemes must be defined |
| `security-applied` | error | Operations must have security requirements |
| `oauth2-scopes` | warning | OAuth2 should define scopes |
| `api-key-header` | warning | API keys should be in header, not query |
| `bearer-format` | info | Bearer tokens should specify format |

### Transport Security

| Rule ID | Severity | Description |
|---------|----------|-------------|
| `https-required` | error | Servers must use HTTPS |
| `no-http-servers` | error | No plain HTTP server URLs |
| `tls-version` | warning | Document minimum TLS version |

### Sensitive Data

| Rule ID | Severity | Description |
|---------|----------|-------------|
| `no-credentials-in-url` | error | No passwords/tokens in URL paths/query |
| `pii-documented` | warning | PII fields should be marked |
| `sensitive-headers` | warning | Sensitive headers should be documented |
| `password-format` | warning | Password fields should use format: password |

### Input Validation

| Rule ID | Severity | Description |
|---------|----------|-------------|
| `string-max-length` | warning | String params should have maxLength |
| `array-max-items` | warning | Array params should have maxItems |
| `number-bounds` | info | Numbers should have min/max bounds |
| `enum-values` | info | Use enums where applicable |
| `pattern-validation` | info | Use regex patterns for structured strings |

### OWASP Top 10 Related

| Rule ID | Severity | Description |
|---------|----------|-------------|
| `injection-prevention` | warning | Document input sanitization |
| `rate-limiting` | warning | Document rate limiting |
| `error-disclosure` | warning | Error responses shouldn't leak internals |
| `cors-configured` | info | CORS policy should be documented |

## PII Detection Patterns

The skill scans for common PII field names:

```
Personal: name, firstName, lastName, fullName, email, phone, mobile, address
Financial: cpf, cnpj, ssn, taxId, accountNumber, cardNumber, cvv, pan
Sensitive: password, secret, token, credential, apiKey, privateKey
```

## Output Format

```json
{
  "rule": "security-applied",
  "severity": "error",
  "message": "Operation POST /payments has no security requirement",
  "path": "paths./payments.post",
  "risk": "Endpoint may be accessible without authentication",
  "fix_suggestion": "Add security requirement: security: [{ bearerAuth: [] }]",
  "owasp_category": "A01:2021 – Broken Access Control",
  "cwe_id": "CWE-306"
}
```

## Security Score Calculation

```
Security Score = 100 - (errors * 15) - (warnings * 5) - (info * 1)
```

| Score | Rating | Description |
|-------|--------|-------------|
| 90-100 | A | Excellent security posture |
| 80-89 | B | Good, minor improvements needed |
| 70-79 | C | Acceptable, address warnings |
| 60-69 | D | Poor, significant issues |
| <60 | F | Critical, immediate action required |

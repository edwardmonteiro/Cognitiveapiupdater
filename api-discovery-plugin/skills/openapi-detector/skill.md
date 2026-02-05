# OpenAPI/Swagger Detector Skill

## Purpose
Detects, fetches, and parses OpenAPI/Swagger specifications from API endpoints. Extracts metadata including API version, endpoints, methods, authentication, and server information.

## Detection Strategy

### Step 1: Check Common OpenAPI Paths

For a given base URL, test these paths in order:

| Path | Format | Spec Version |
|------|--------|-------------|
| `/openapi.json` | JSON | OpenAPI 3.x |
| `/openapi.yaml` | YAML | OpenAPI 3.x |
| `/openapi.yml` | YAML | OpenAPI 3.x |
| `/swagger.json` | JSON | Swagger 2.0 |
| `/swagger.yaml` | YAML | Swagger 2.0 |
| `/api-docs` | JSON | Spring Boot |
| `/api-docs.json` | JSON | Various |
| `/v3/api-docs` | JSON | Spring Boot 3 |
| `/v2/api-docs` | JSON | Spring Boot 2 |
| `/swagger/v1/swagger.json` | JSON | ASP.NET |
| `/docs` | HTML | FastAPI |
| `/redoc` | HTML | ReDoc UI |
| `/_catalog` | JSON | Custom |

### Step 2: Check Response Content

Validate the response actually contains an OpenAPI/Swagger specification:

**OpenAPI 3.x indicators:**
```json
{
  "openapi": "3.0.0",
  "info": { "title": "...", "version": "..." },
  "paths": { ... }
}
```

**Swagger 2.0 indicators:**
```json
{
  "swagger": "2.0",
  "info": { "title": "...", "version": "..." },
  "paths": { ... }
}
```

### Step 3: Parse Spec Metadata

Extract the following fields from the specification:

```json
{
  "has_openapi": true,
  "openapi_url": "https://api.example.com/openapi.json",
  "spec_format": "openapi3",
  "openapi_version": "3.0.3",
  "api_info": {
    "title": "Payment API",
    "version": "2.1.0",
    "description": "Payment processing API",
    "contact": {
      "name": "Payments Squad",
      "email": "payments@example.com"
    },
    "license": "Apache-2.0"
  },
  "total_endpoints": 24,
  "endpoints_by_method": {
    "GET": 12,
    "POST": 8,
    "PUT": 3,
    "DELETE": 1
  },
  "paths": [
    "/payments",
    "/payments/{id}",
    "/payments/{id}/refund"
  ],
  "authentication": {
    "types": ["oauth2", "apiKey"],
    "oauth2_flows": ["client_credentials"],
    "api_key_location": "header"
  },
  "servers": [
    {
      "url": "https://api.example.com/v2",
      "description": "Production"
    },
    {
      "url": "https://sandbox.example.com/v2",
      "description": "Sandbox"
    }
  ],
  "tags": ["payments", "transfers", "refunds"],
  "has_examples": true,
  "has_schemas": true,
  "schema_count": 45,
  "deprecated_endpoints": 2
}
```

## Parsing Logic

### Count Endpoints
```python
def count_endpoints(spec):
    total = 0
    by_method = {}
    for path, methods in spec.get("paths", {}).items():
        for method in methods:
            if method.lower() in ("get", "post", "put", "patch", "delete", "head", "options"):
                total += 1
                by_method[method.upper()] = by_method.get(method.upper(), 0) + 1
    return total, by_method
```

### Extract Authentication
```python
def extract_auth(spec):
    # OpenAPI 3.x
    security_schemes = spec.get("components", {}).get("securitySchemes", {})
    # Swagger 2.0
    if not security_schemes:
        security_schemes = spec.get("securityDefinitions", {})

    types = []
    for name, scheme in security_schemes.items():
        types.append(scheme.get("type", "unknown"))

    return types
```

### Extract Servers
```python
def extract_servers(spec):
    # OpenAPI 3.x
    servers = spec.get("servers", [])
    # Swagger 2.0
    if not servers and "host" in spec:
        scheme = (spec.get("schemes") or ["https"])[0]
        servers = [{"url": f"{scheme}://{spec['host']}{spec.get('basePath', '/')}"}]
    return servers
```

## Validation Checks

After parsing, verify:

1. **Spec validity**: Does it have required fields (`info`, `paths`)?
2. **Endpoint coverage**: Are all endpoints documented?
3. **Schema completeness**: Do endpoints have request/response schemas?
4. **Example availability**: Are there request/response examples?
5. **Authentication defined**: Is security configured?

## Output Quality Indicators

```json
{
  "quality_score": 75,
  "issues": [
    "3 endpoints missing response schemas",
    "No request examples provided",
    "2 deprecated endpoints without replacement"
  ]
}
```

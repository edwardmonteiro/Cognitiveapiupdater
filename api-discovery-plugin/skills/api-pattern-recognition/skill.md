# API Pattern Recognition Skill

## Purpose
Recognizes API type patterns from URLs, HTTP headers, response bodies, and endpoint structures. This is the core classification engine that determines whether an API is REST, GraphQL, SOAP, or gRPC.

## Input
The skill receives an API's URL, HTTP headers, and optionally a response body sample.

## Classification Rules

### REST API Detection
**Confidence: High (>0.8) when 3+ indicators match:**

| Indicator | Weight | Pattern |
|-----------|--------|---------|
| URL path contains `/api/` | 0.2 | `/api/v1/resources` |
| URL path contains `/v{N}/` | 0.2 | `/v2/payments` |
| Content-Type is `application/json` | 0.2 | `Content-Type: application/json` |
| Response is valid JSON object/array | 0.15 | `{"data": [...]}` |
| Uses RESTful resource naming | 0.15 | Nouns: `/users`, `/orders`, `/payments` |
| Multiple HTTP methods supported | 0.1 | GET, POST, PUT, DELETE on same base |
| Has OpenAPI/Swagger spec | 0.2 | `/swagger.json`, `/openapi.yaml` |
| HATEOAS links in response | 0.1 | `"_links": {"self": {...}}` |

**URL patterns:**
```
/api/v1/resources
/api/resources/{id}
/v2/payments
/rest/services/data
```

**Anti-patterns (reduce REST confidence):**
- POST-only endpoint → might be GraphQL or RPC
- XML response → might be SOAP
- Binary content → might be gRPC

### GraphQL API Detection
**Confidence: High (>0.8) when 2+ indicators match:**

| Indicator | Weight | Pattern |
|-----------|--------|---------|
| URL path is `/graphql` | 0.4 | `POST /graphql` |
| POST body contains `"query"` key | 0.3 | `{"query": "{ users { id } }"}` |
| Response has `"data"` root key | 0.2 | `{"data": {"users": [...]}}` |
| Response has `"errors"` key | 0.15 | `{"errors": [{"message": "..."}]}` |
| Introspection query works | 0.3 | `__schema` returns types |
| Single endpoint, all POST | 0.2 | Only `/graphql` endpoint |

**URL patterns:**
```
/graphql
/gql
/api/graphql
/v1/graphql
```

### SOAP API Detection
**Confidence: High (>0.8) when 2+ indicators match:**

| Indicator | Weight | Pattern |
|-----------|--------|---------|
| URL ends with `.asmx` or `.svc` | 0.3 | `/service.asmx` |
| Content-Type is `text/xml` | 0.3 | `Content-Type: text/xml` |
| Content-Type is `application/soap+xml` | 0.3 | SOAP 1.2 |
| Response contains SOAP envelope | 0.3 | `<soap:Envelope ...>` |
| WSDL available at `?wsdl` | 0.3 | `https://host/service?wsdl` |
| SOAPAction header present | 0.2 | `SOAPAction: "urn:action"` |
| Namespace references SOAP | 0.2 | `xmlns:soap=` |

**URL patterns:**
```
/services/PaymentService.asmx
/ws/AccountService.svc
/soap/v1/credit
```

### gRPC API Detection
**Confidence: High (>0.8) when 2+ indicators match:**

| Indicator | Weight | Pattern |
|-----------|--------|---------|
| Content-Type is `application/grpc` | 0.4 | gRPC protocol |
| HTTP/2 protocol | 0.2 | Required for gRPC |
| Port 50051 | 0.2 | Default gRPC port |
| gRPC reflection works | 0.3 | `grpc.reflection.v1alpha` |
| Binary protobuf response | 0.2 | Non-text response body |
| `grpc-status` header | 0.3 | `grpc-status: 0` |

**URL patterns:**
```
host:50051/package.Service/Method
```

## Decision Algorithm

```python
def classify(url, headers, body):
    scores = {
        "REST": calculate_rest_score(url, headers, body),
        "GraphQL": calculate_graphql_score(url, headers, body),
        "SOAP": calculate_soap_score(url, headers, body),
        "gRPC": calculate_grpc_score(url, headers, body),
    }

    best_type = max(scores, key=scores.get)
    confidence = scores[best_type]

    if confidence < 0.3:
        return "unknown", confidence

    return best_type, min(confidence, 1.0)
```

## Output Format

```json
{
  "api_type": "REST",
  "confidence": 0.85,
  "indicators_matched": [
    "URL contains /api/v1/",
    "Content-Type: application/json",
    "Valid JSON response",
    "RESTful resource naming"
  ],
  "indicators_not_matched": [
    "No HATEOAS links"
  ]
}
```

## Edge Cases

1. **REST-like GraphQL**: Some GraphQL APIs are mounted at `/api/graphql` - check for GraphQL query format in body
2. **JSON SOAP**: Modern SOAP can use JSON - check for SOAP envelope markers
3. **REST over gRPC (gRPC-Web)**: Uses `application/grpc-web` content type
4. **Hybrid APIs**: Some APIs expose both REST and GraphQL - report both with individual confidence scores

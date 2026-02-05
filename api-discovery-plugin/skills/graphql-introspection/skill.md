# GraphQL Introspection Skill

## Purpose
Performs GraphQL introspection queries to discover schema, types, queries, mutations, and subscriptions. Assesses schema completeness and identifies security concerns.

## Detection Strategy

### Step 1: Identify GraphQL Endpoint

Test these paths with a POST request:

| Path | Notes |
|------|-------|
| `/graphql` | Most common |
| `/gql` | Short form |
| `/api/graphql` | Namespaced |
| `/v1/graphql` | Versioned |
| `/graphql/v1` | Alt versioned |
| `/query` | Hasura style |

### Step 2: Test Introspection

Send the introspection query:

```graphql
{
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      name
      kind
      description
      fields {
        name
        description
        type {
          name
          kind
          ofType {
            name
            kind
          }
        }
        args {
          name
          type {
            name
            kind
          }
        }
      }
    }
    directives {
      name
      description
    }
  }
}
```

**HTTP Request:**
```
POST /graphql HTTP/1.1
Content-Type: application/json

{
  "query": "{ __schema { queryType { name } mutationType { name } subscriptionType { name } types { name kind description fields { name description type { name kind ofType { name kind } } args { name type { name kind } } } } directives { name description } } }"
}
```

### Step 3: Parse Schema

Extract the following from introspection results:

```json
{
  "has_graphql_schema": true,
  "introspection_enabled": true,
  "endpoint": "/graphql",
  "schema": {
    "queries": [
      {
        "name": "getPayment",
        "args": ["id: ID!"],
        "return_type": "Payment"
      },
      {
        "name": "listPayments",
        "args": ["limit: Int", "offset: Int"],
        "return_type": "[Payment]"
      }
    ],
    "mutations": [
      {
        "name": "createPayment",
        "args": ["input: PaymentInput!"],
        "return_type": "Payment"
      }
    ],
    "subscriptions": [
      {
        "name": "onPaymentStatusChange",
        "args": ["paymentId: ID!"],
        "return_type": "PaymentEvent"
      }
    ],
    "types": {
      "custom": 25,
      "input": 10,
      "enum": 5,
      "interface": 2,
      "union": 1
    },
    "total_fields": 150,
    "total_queries": 15,
    "total_mutations": 8,
    "total_subscriptions": 3
  }
}
```

## Security Assessment

### Introspection Enabled (Security Risk)

If introspection is enabled in production:

```json
{
  "security_concerns": [
    {
      "severity": "medium",
      "issue": "GraphQL introspection enabled in production",
      "description": "Introspection exposes the complete API schema including all types, queries, and mutations. This can aid attackers in understanding the API surface.",
      "recommendation": "Disable introspection in production. Use schema documentation tools instead."
    }
  ]
}
```

### Other Security Checks

| Check | Risk | Description |
|-------|------|-------------|
| Introspection enabled | Medium | Schema exposure |
| No query depth limit | High | DoS via nested queries |
| No query complexity limit | High | Resource exhaustion |
| Mutations without auth | Critical | Unauthorized data modification |
| PII in type names | Low | Information disclosure |

## Schema Analysis

### Type Classification

Filter out built-in GraphQL types:

```python
BUILTIN_TYPES = {"String", "Int", "Float", "Boolean", "ID",
                  "__Schema", "__Type", "__Field", "__InputValue",
                  "__EnumValue", "__Directive", "__DirectiveLocation"}

custom_types = [t for t in types if t["name"] not in BUILTIN_TYPES
                and not t["name"].startswith("__")]
```

### Complexity Score

```python
def schema_complexity(schema):
    types = len(schema["types"]["custom"])
    queries = schema["total_queries"]
    mutations = schema["total_mutations"]
    fields = schema["total_fields"]

    if fields > 500 or types > 100:
        return "high"
    elif fields > 100 or types > 30:
        return "medium"
    return "low"
```

## Output Format

```json
{
  "has_graphql_schema": true,
  "introspection_enabled": true,
  "endpoint": "https://api.example.com/graphql",
  "schema_summary": {
    "total_queries": 15,
    "total_mutations": 8,
    "total_subscriptions": 3,
    "custom_types": 25,
    "total_fields": 150,
    "complexity": "medium"
  },
  "security_concerns": [],
  "top_queries": ["getPayment", "listPayments", "getAccount"],
  "top_mutations": ["createPayment", "updatePayment"]
}
```

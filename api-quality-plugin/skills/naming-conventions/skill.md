# Naming Conventions Skill

## Purpose
Enforces consistent naming conventions across OpenAPI specifications for paths, parameters, schemas, and properties.

## Convention Rules

### Path Segments
**Convention:** kebab-case (lowercase with hyphens)

| Good | Bad |
|------|-----|
| `/user-accounts` | `/userAccounts` |
| `/payment-methods` | `/PaymentMethods` |
| `/credit-cards/{cardId}` | `/credit_cards/{card_id}` |

**Rule ID:** `path-segment-kebab-case`

### Path Parameters
**Convention:** camelCase

| Good | Bad |
|------|-----|
| `{userId}` | `{user_id}` |
| `{accountNumber}` | `{account-number}` |
| `{transactionId}` | `{TransactionId}` |

**Rule ID:** `path-param-camel-case`

### Query Parameters
**Convention:** camelCase

| Good | Bad |
|------|-----|
| `?pageSize=10` | `?page_size=10` |
| `?sortOrder=asc` | `?sort-order=asc` |
| `?includeDeleted=true` | `?IncludeDeleted=true` |

**Rule ID:** `query-param-camel-case`

### Header Parameters
**Convention:** Train-Case (HTTP standard)

| Good | Bad |
|------|-----|
| `X-Request-Id` | `x-request-id` |
| `X-Correlation-Id` | `x_correlation_id` |
| `Authorization` | `authorization` |

**Rule ID:** `header-param-train-case`

### Schema Names (Components)
**Convention:** PascalCase

| Good | Bad |
|------|-----|
| `UserAccount` | `userAccount` |
| `PaymentRequest` | `payment_request` |
| `CreditCardResponse` | `credit-card-response` |

**Rule ID:** `schema-name-pascal-case`

### Schema Properties
**Convention:** camelCase

| Good | Bad |
|------|-----|
| `firstName` | `first_name` |
| `accountBalance` | `account-balance` |
| `createdAt` | `CreatedAt` |

**Rule ID:** `property-camel-case`

### Operation IDs
**Convention:** camelCase, verb + noun pattern

| Good | Bad |
|------|-----|
| `getUser` | `get_user` |
| `createPayment` | `CreatePayment` |
| `listTransactions` | `list-transactions` |

**Rule ID:** `operation-id-camel-case`

## Configuration

```yaml
naming_conventions:
  path_segments: kebab-case
  path_parameters: camelCase
  query_parameters: camelCase
  header_parameters: Train-Case
  schema_names: PascalCase
  schema_properties: camelCase
  operation_ids: camelCase

  # Exceptions (regex patterns)
  exceptions:
    - pattern: "^id$"  # Allow 'id' as-is
    - pattern: "^url$" # Allow 'url' as-is
```

## Output Format

```json
{
  "rule": "path-segment-kebab-case",
  "severity": "warning",
  "message": "Path segment 'userAccounts' should be 'user-accounts'",
  "path": "paths./userAccounts",
  "current": "userAccounts",
  "expected": "user-accounts",
  "fix_suggestion": "Rename path to '/user-accounts'"
}
```

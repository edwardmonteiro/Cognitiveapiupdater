# SOAP/WSDL Parser Skill

## Purpose
Detects SOAP APIs and parses their WSDL definitions to extract available operations, data types, bindings, and service endpoints.

## Detection Strategy

### Step 1: Identify SOAP Endpoints

**URL indicators:**

| Pattern | Example |
|---------|---------|
| `.asmx` suffix | `/PaymentService.asmx` |
| `.svc` suffix | `/AccountService.svc` |
| `/ws/` path | `/ws/credit` |
| `/services/` path | `/services/notification` |
| `/soap/` path | `/soap/v1/transfer` |
| `?wsdl` parameter | `?wsdl` returns XML |

**HTTP indicators:**

| Header | Value | SOAP Version |
|--------|-------|-------------|
| Content-Type | `text/xml` | SOAP 1.1 |
| Content-Type | `application/soap+xml` | SOAP 1.2 |
| SOAPAction | `"urn:action"` | SOAP 1.1 |
| Accept | `text/xml` | SOAP |

**Response body indicators:**
```xml
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    ...
  </soap:Body>
</soap:Envelope>
```

### Step 2: Fetch WSDL

Try fetching WSDL from:
1. `{url}?wsdl`
2. `{url}?WSDL`
3. `{url}?singleWsdl`
4. `{url}/wsdl`

### Step 3: Parse WSDL

WSDL 1.1 structure:
```xml
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/">
  <types>
    <schema>...</schema>
  </types>
  <message name="...">...</message>
  <portType name="...">
    <operation name="...">...</operation>
  </portType>
  <binding name="..." type="...">...</binding>
  <service name="...">
    <port name="..." binding="...">
      <soap:address location="..."/>
    </port>
  </service>
</definitions>
```

WSDL 2.0 structure:
```xml
<description xmlns="http://www.w3.org/ns/wsdl">
  <types>...</types>
  <interface name="...">
    <operation name="...">...</operation>
  </interface>
  <binding name="..." interface="..." type="...">...</binding>
  <service name="..." interface="...">
    <endpoint name="..." binding="..." address="..."/>
  </service>
</description>
```

## Extraction Logic

### Extract Operations
```python
def extract_operations(wsdl_root):
    operations = []
    # WSDL 1.1: portType > operation
    for port_type in wsdl_root.findall('.//portType'):
        for op in port_type.findall('operation'):
            operations.append({
                "name": op.get("name"),
                "input": extract_message_parts(op.find("input")),
                "output": extract_message_parts(op.find("output")),
                "faults": [f.get("name") for f in op.findall("fault")],
            })
    return operations
```

### Extract Service Endpoints
```python
def extract_endpoints(wsdl_root):
    endpoints = []
    for service in wsdl_root.findall('.//service'):
        for port in service.findall('port'):
            address = port.find('.//{http://schemas.xmlsoap.org/wsdl/soap/}address')
            if address is not None:
                endpoints.append({
                    "service": service.get("name"),
                    "port": port.get("name"),
                    "location": address.get("location"),
                })
    return endpoints
```

### Extract Data Types
```python
def extract_types(wsdl_root):
    types = []
    schema = wsdl_root.find('.//{http://www.w3.org/2001/XMLSchema}schema')
    if schema is not None:
        for complex_type in schema.findall('{http://www.w3.org/2001/XMLSchema}complexType'):
            types.append({
                "name": complex_type.get("name"),
                "elements": extract_elements(complex_type),
            })
    return types
```

## Output Format

```json
{
  "has_wsdl": true,
  "wsdl_url": "https://host/PaymentService.asmx?wsdl",
  "wsdl_version": "1.1",
  "soap_version": "1.1",
  "service_info": {
    "name": "PaymentService",
    "namespace": "http://example.com/payment",
    "documentation": "Payment processing service"
  },
  "operations": [
    {
      "name": "ProcessPayment",
      "input_message": "ProcessPaymentRequest",
      "output_message": "ProcessPaymentResponse",
      "faults": ["PaymentFault"],
      "soap_action": "http://example.com/payment/ProcessPayment"
    },
    {
      "name": "GetPaymentStatus",
      "input_message": "GetPaymentStatusRequest",
      "output_message": "GetPaymentStatusResponse",
      "faults": [],
      "soap_action": "http://example.com/payment/GetPaymentStatus"
    }
  ],
  "total_operations": 8,
  "endpoints": [
    {
      "service": "PaymentService",
      "port": "PaymentServiceSoap",
      "location": "https://api.example.com/PaymentService.asmx"
    }
  ],
  "types": {
    "complex_types": 12,
    "simple_types": 5,
    "elements": 30
  },
  "bindings": [
    {
      "name": "PaymentServiceSoap",
      "transport": "http://schemas.xmlsoap.org/soap/http",
      "style": "document"
    }
  ],
  "imports": [],
  "legacy_indicators": {
    "uses_rpc_style": false,
    "uses_encoded": false,
    "soap_version": "1.1",
    "migration_complexity": "medium"
  }
}
```

## Migration Assessment

For SOAP-to-REST migration planning:

```json
{
  "migration_assessment": {
    "complexity": "medium",
    "estimated_rest_endpoints": 8,
    "considerations": [
      "8 operations can map to REST resources",
      "Complex types may need JSON schema redesign",
      "SOAP faults need to map to HTTP status codes"
    ],
    "suggested_rest_mapping": [
      {"soap_operation": "ProcessPayment", "rest": "POST /payments"},
      {"soap_operation": "GetPaymentStatus", "rest": "GET /payments/{id}/status"},
      {"soap_operation": "ListPayments", "rest": "GET /payments"}
    ]
  }
}
```

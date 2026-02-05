# Framework Fingerprinting Skill

## Purpose
Identifies the technology stack (programming language, framework, web server, cloud provider) of an API by analyzing HTTP response headers, error pages, default endpoints, and response patterns.

## Detection Rules

### Language Detection

| Language | Header/Indicator | Detection Pattern |
|----------|-----------------|-------------------|
| **Java** | `X-Application-Context` | Spring Boot |
| **Java** | `X-Java-Version` | JVM version exposed |
| **Java** | Server contains `Tomcat` | Apache Tomcat |
| **Java** | Server contains `Jetty` | Eclipse Jetty |
| **Java** | Cookie `JSESSIONID` | Java Servlet container |
| **Python** | Server: `gunicorn` | Gunicorn WSGI |
| **Python** | Server: `uvicorn` | Uvicorn ASGI |
| **Python** | Server: `WSGIServer` | Django dev server |
| **Python** | Server: `daphne` | Django Channels |
| **Node.js** | `X-Powered-By: Express` | Express.js |
| **Node.js** | `X-Powered-By: Next.js` | Next.js API routes |
| **Node.js** | `X-Powered-By: Fastify` | Fastify |
| **.NET** | Server: `Kestrel` | ASP.NET Core |
| **.NET** | `X-AspNet-Version` | ASP.NET Framework |
| **.NET** | `X-AspNetMvc-Version` | ASP.NET MVC |
| **.NET** | `X-Powered-By: ASP.NET` | ASP.NET |
| **Go** | Server: `Go` | Go net/http |
| **Go** | No `Server` + small response | Go minimal server |
| **Ruby** | Server: `Puma` | Puma (Rails) |
| **Ruby** | Server: `Unicorn` | Unicorn (Rails) |
| **Ruby** | `X-Runtime` header | Rails |
| **PHP** | `X-Powered-By: PHP` | PHP version |
| **PHP** | Server: `Apache + PHP` | PHP on Apache |
| **Rust** | Server: `Actix` | Actix Web |
| **Rust** | Server: `Warp` | Warp framework |

### Framework Detection

| Framework | Detection Method |
|-----------|-----------------|
| **Spring Boot** | `X-Application-Context` header |
| **Spring Boot** | `/actuator/health` returns JSON |
| **Spring Boot** | `/actuator/info` returns JSON |
| **Spring Boot** | `/v3/api-docs` returns OpenAPI |
| **Django** | `csrftoken` cookie |
| **Django** | Server: `WSGIServer` |
| **Django REST** | Default browsable API HTML page |
| **FastAPI** | `/docs` returns Swagger UI |
| **FastAPI** | `/redoc` returns ReDoc |
| **FastAPI** | `/openapi.json` returns spec |
| **Flask** | Server: `Werkzeug` |
| **Express** | `X-Powered-By: Express` |
| **NestJS** | `X-Powered-By: Express` + structured errors |
| **ASP.NET Core** | Server: `Kestrel` |
| **Rails** | `X-Runtime` + `X-Request-Id` headers |
| **Laravel** | `laravel_session` cookie |
| **Gin** | Server: `Gin` or minimal Go server |
| **Fiber** | Server: `Fiber` |

### Web Server / Reverse Proxy Detection

| Server | Header Pattern |
|--------|---------------|
| **Nginx** | `Server: nginx` or `Server: nginx/1.x` |
| **Apache** | `Server: Apache` or `Server: Apache/2.x` |
| **IIS** | `Server: Microsoft-IIS` |
| **Caddy** | `Server: Caddy` |
| **Traefik** | Custom headers or default error page |
| **HAProxy** | `Via` header or custom headers |
| **Envoy** | `Server: envoy` or `x-envoy-*` headers |

### Cloud / Infrastructure Detection

| Provider | Header / Pattern |
|----------|-----------------|
| **AWS** | `X-Amz-*` or `X-Amzn-*` headers |
| **AWS API Gateway** | `x-amzn-RequestId`, `x-amz-apigw-id` |
| **AWS Lambda** | `X-Amzn-Trace-Id` |
| **AWS CloudFront** | `X-Cache`, `Via: cloudfront` |
| **AWS ALB** | `X-Amzn-Trace-Id` with ELB pattern |
| **Azure** | `X-Azure-*` headers |
| **Azure API Mgmt** | `Ocp-Apim-*` headers |
| **Azure App Service** | `X-Ms-*` headers |
| **GCP** | `X-Cloud-Trace-Context` |
| **GCP Cloud Run** | `X-Cloud-Trace-Context` + short cold starts |
| **Cloudflare** | `CF-RAY`, `cf-*` headers |
| **Vercel** | `X-Vercel-*` headers |
| **Heroku** | `Via: heroku`, `X-Request-Id` pattern |
| **Netlify** | `X-NF-Request-ID` |

### API Gateway Detection

| Gateway | Detection Method |
|---------|-----------------|
| **Kong** | `Via: kong/x.x`, `X-Kong-*` headers |
| **Apigee** | `X-Apigee-*` headers |
| **Mulesoft** | `X-Mule-*` headers |
| **Tyk** | `X-Tyk-*` headers |
| **AWS API Gateway** | `x-amzn-RequestId` format |
| **Azure APIM** | `Ocp-Apim-Subscription-Key` requirement |

## Fingerprinting Process

```python
def fingerprint(headers, url, status_code, body):
    result = {
        "language": detect_language(headers),
        "framework": detect_framework(headers, url, body),
        "server": detect_server(headers),
        "cloud": detect_cloud(headers),
        "api_gateway": detect_gateway(headers),
        "confidence": 0.0,
        "indicators": [],
    }

    # Calculate confidence based on indicators matched
    indicators = len(result["indicators"])
    result["confidence"] = min(indicators * 0.2, 1.0)

    return result
```

## Endpoint Probing

For deeper detection, optionally probe:

| Endpoint | Detects |
|----------|---------|
| `/actuator/health` | Spring Boot |
| `/actuator/info` | Spring Boot version |
| `/docs` | FastAPI |
| `/swagger-ui/` | Spring Boot + Swagger |
| `/__health` | Various |
| `/healthz` | Kubernetes |
| `/metrics` | Prometheus endpoint |
| `/debug/vars` | Go debug |

## Output Format

```json
{
  "technology": {
    "language": "java",
    "language_version": "",
    "framework": "spring-boot",
    "framework_version": "3.2.0",
    "server": "nginx",
    "server_version": "1.24",
    "cloud": "aws",
    "cloud_services": ["api-gateway", "lambda"],
    "api_gateway": "kong",
    "container_platform": "kubernetes",
    "confidence": 0.85,
    "indicators": [
      "X-Application-Context header (Spring Boot)",
      "/actuator/health returns 200 (Spring Boot)",
      "Server: nginx (Nginx reverse proxy)",
      "X-Amzn-Trace-Id (AWS infrastructure)"
    ]
  }
}
```

# Authentication Architecture

## Overview

Authentication uses Amazon Cognito as the OAuth2/OIDC identity provider with Authorization Code flow + PKCE. The Application Service validates JWTs on every request, checking signature, expiry, audience, and group membership for role-based access control.

## Authentication Flow

```mermaid
sequenceDiagram
    participant Client as API Client
    participant CF as CloudFront
    participant APIGW as API Gateway
    participant WAF as WAF
    participant ALB as ALB
    participant App as Application Service
    participant Cognito as Cognito User Pool
    participant Redis as Redis (Sessions)
    participant Aurora as Aurora (Users)

    Note over Client,Cognito: Step 1: Token Acquisition
    Client->>Cognito: POST /oauth2/authorize (PKCE challenge)
    Cognito-->>Client: Authorization code
    Client->>Cognito: POST /oauth2/token (code + PKCE verifier)
    Cognito-->>Client: Access Token (JWT) + Refresh Token

    Note over Client,Aurora: Step 2: Authenticated API Request
    Client->>CF: GET /api/products (Bearer token)
    CF->>APIGW: Forward (cache miss or no-cache)
    APIGW->>WAF: Request inspection
    WAF->>ALB: Pass (no threats detected)
    ALB->>App: Forward to healthy target

    Note over App: Step 3: Token Validation
    App->>App: Verify JWT signature (JWKS)
    App->>App: Check token expiry
    App->>App: Validate audience claim
    App->>App: Extract group membership

    Note over App,Aurora: Step 4: Authorization & Data
    App->>App: Check group permissions for resource
    App->>Redis: GET session/cache data
    alt Cache Hit
        Redis-->>App: Cached response
    else Cache Miss
        App->>Aurora: Query database
        Aurora-->>App: Results
        App->>Redis: SET cache (TTL 60s)
    end
    App-->>Client: 200 JSON Response
```

## Cognito Configuration

### User Pool Settings

| Setting | Value | Rationale |
|---------|-------|-----------|
| Sign-up | Email-based | Standard SaaS pattern |
| Email verification | Required | Prevent fake accounts |
| MFA | Optional (TOTP) | Available for admin users |
| Password policy | Min 12 chars, upper + lower + number + symbol | Enterprise standard |
| Token validity (access) | 1 hour | Limits exposure window |
| Token validity (refresh) | 30 days | Good UX for returning users |

### OAuth2 Client Configuration

| Parameter | Value |
|-----------|-------|
| Flow | Authorization Code with PKCE |
| Scopes | openid, email, profile |
| Callback URLs | Configurable per environment |
| Logout URLs | Configurable per environment |

### User Pool Groups (RBAC)

| Group | Permissions | Use Case |
|-------|------------|----------|
| admin | Full CRUD on all resources | Platform administrators |
| manager | Read all + write products/orders | Operational managers |
| viewer | Read-only access | Report consumers, auditors |

## JWT Token Structure

### Access Token Claims

```json
{
  "sub": "user-uuid",
  "iss": "https://cognito-idp.eu-west-2.amazonaws.com/eu-west-2_xxxxx",
  "aud": "client-id",
  "token_use": "access",
  "scope": "openid email profile",
  "cognito:groups": ["manager"],
  "exp": 1705334400,
  "iat": 1705330800
}
```

### Validation Checks

```mermaid
flowchart TD
    Token[Incoming JWT] --> Sig{Signature valid?<br/>JWKS verification}
    Sig -->|No| R401a[401 Unauthorized]
    Sig -->|Yes| Exp{Token expired?}
    Exp -->|Yes| R401b[401 Unauthorized]
    Exp -->|No| Aud{Audience matches<br/>client ID?}
    Aud -->|No| R401c[401 Unauthorized]
    Aud -->|Yes| Groups{Has required group<br/>for resource?}
    Groups -->|No| R403[403 Forbidden]
    Groups -->|Yes| Allow[Process Request]
```

### Validation Steps (in order)

1. **Signature verification**: Validate against Cognito JWKS endpoint (public keys cached locally)
2. **Expiry check**: `exp` claim must be in the future
3. **Audience check**: `aud` must match the configured Cognito client ID
4. **Group membership**: `cognito:groups` must include a group with permission for the requested resource/action

## Authorization Matrix

| Resource | Action | admin | manager | viewer |
|----------|--------|-------|---------|--------|
| Products | Read | ✅ | ✅ | ✅ |
| Products | Create/Update | ✅ | ✅ | ❌ |
| Products | Delete | ✅ | ❌ | ❌ |
| Orders | Read (own) | ✅ | ✅ | ✅ |
| Orders | Read (all) | ✅ | ✅ | ❌ |
| Orders | Create | ✅ | ✅ | ❌ |
| Users | Read | ✅ | ❌ | ❌ |
| Users | Manage | ✅ | ❌ | ❌ |

## Session Management

### Session Flow

```mermaid
sequenceDiagram
    participant App as Application
    participant Redis as Redis

    Note over App,Redis: Session Creation (on login)
    App->>Redis: SET session:{id} {user_id, email, role, groups, created_at}
    App->>Redis: EXPIRE session:{id} 3600

    Note over App,Redis: Session Access (on request)
    App->>Redis: GET session:{id}
    Redis-->>App: Session data
    App->>Redis: EXPIRE session:{id} 3600 (refresh TTL)

    Note over App,Redis: Session Destruction (on logout)
    App->>Redis: DEL session:{id}
```

### Session Data Structure

```json
{
  "user_id": "uuid-string",
  "email": "user@example.com",
  "role": "manager",
  "groups": ["manager"],
  "created_at": 1705330800.0,
  "last_accessed": 1705334400.0,
  "metadata": {}
}
```

## Error Responses

### 401 Unauthorized

```json
{
  "error": "unauthorized",
  "message": "Token validation failed: [reason]",
  "request_id": "req-abc123"
}
```

### 403 Forbidden

```json
{
  "error": "forbidden",
  "message": "Insufficient permissions for this resource",
  "request_id": "req-abc123"
}
```

## JWKS Caching

- Public keys cached locally in the application
- Cache TTL: 24 hours (keys rotate infrequently)
- Cache refresh: On signature verification failure, refresh keys once before rejecting
- Prevents repeated network calls to Cognito JWKS endpoint

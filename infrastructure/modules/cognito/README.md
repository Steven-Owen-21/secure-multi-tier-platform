# Cognito Module

Creates an AWS Cognito User Pool with OAuth2/OIDC authentication, user registration, email verification, and role-based access control groups for the platform.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Cognito User Pool                                                │
│                                                                   │
│  ┌─────────────────────────┐  ┌─────────────────────────┐       │
│  │ Sign-up                  │  │ Password Policy          │       │
│  │ • Email-based            │  │ • Min 12 characters      │       │
│  │ • Email verification     │  │ • Uppercase required     │       │
│  │ • Account recovery       │  │ • Lowercase required     │       │
│  └─────────────────────────┘  │ • Number required        │       │
│                                │ • Symbol required        │       │
│  ┌─────────────────────────┐  └─────────────────────────┘       │
│  │ User Pool Client         │                                     │
│  │ • Auth Code + PKCE       │  ┌─────────────────────────┐       │
│  │ • Access token: 1h       │  │ Groups (RBAC)            │       │
│  │ • Refresh token: 30d     │  │ • admin (precedence 1)   │       │
│  │ • Scopes: openid, email, │  │ • manager (precedence 10)│       │
│  │   profile                │  │ • viewer (precedence 100)│       │
│  └─────────────────────────┘  └─────────────────────────┘       │
│                                                                   │
│  Hosted UI Domain: {project}-{env}-auth                          │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **Email-based sign-up**: Users register with email, verification code required
- **Strong password policy**: Minimum 12 characters with uppercase, lowercase, numbers, and symbols
- **Authorization Code + PKCE**: Secure OAuth2 flow for public clients (no client secret)
- **Token configuration**: Access token 1h expiry, refresh token 30d expiry
- **Role-based groups**: admin, manager, viewer with IAM role mappings
- **Advanced security**: Enforced adaptive authentication for threat protection
- **User existence error prevention**: Prevents enumeration attacks

## Usage

```hcl
module "cognito" {
  source = "./modules/cognito"

  callback_urls = ["https://app.example.com/callback", "http://localhost:3000/callback"]
  logout_urls   = ["https://app.example.com/logout", "http://localhost:3000/logout"]

  admin_role_arn   = module.iam.admin_role_arn
  manager_role_arn = module.iam.manager_role_arn
  viewer_role_arn  = module.iam.viewer_role_arn

  environment  = "demo"
  project_name = "secure-multi-tier-platform"
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `callback_urls` | Allowed OAuth2 callback/redirect URIs | `list(string)` | n/a | yes |
| `logout_urls` | Allowed logout/sign-out URLs | `list(string)` | n/a | yes |
| `environment` | Deployment environment name | `string` | `"demo"` | no |
| `project_name` | Project name for resource naming | `string` | `"secure-multi-tier-platform"` | no |
| `admin_role_arn` | IAM role ARN for admin group | `string` | `""` | no |
| `manager_role_arn` | IAM role ARN for manager group | `string` | `""` | no |
| `viewer_role_arn` | IAM role ARN for viewer group | `string` | `""` | no |
| `access_token_validity` | Access token validity in hours | `number` | `1` | no |
| `refresh_token_validity` | Refresh token validity in days | `number` | `30` | no |
| `password_minimum_length` | Minimum password length | `number` | `12` | no |

## Outputs

| Name | Description |
|------|-------------|
| `user_pool_id` | ID of the Cognito User Pool |
| `user_pool_arn` | ARN of the Cognito User Pool |
| `client_id` | ID of the User Pool Client |
| `jwks_url` | JWKS URL for JWT token verification |
| `user_pool_endpoint` | Endpoint URL of the User Pool |
| `user_pool_domain` | Hosted UI domain name |
| `oauth2_endpoint` | OAuth2 authorization endpoint URL |
| `admin_group_name` | Name of the admin group |
| `manager_group_name` | Name of the manager group |
| `viewer_group_name` | Name of the viewer group |

## Authentication Flow

1. Client initiates Authorization Code flow with PKCE challenge
2. User authenticates via Cognito hosted UI (email + password)
3. Cognito returns authorization code to callback URL
4. Client exchanges code + PKCE verifier for tokens
5. Access token contains `cognito:groups` claim for authorization
6. Application validates JWT using JWKS endpoint

## Groups and Permissions

| Group | Precedence | Description |
|-------|-----------|-------------|
| `admin` | 1 | Full platform access — manage users, products, orders |
| `manager` | 10 | Read/write access to products and orders |
| `viewer` | 100 | Read-only access to products and orders |

Lower precedence numbers indicate higher priority when a user belongs to multiple groups.

## Requirements

| Name | Version |
|------|---------|
| terraform | >= 1.5.0 |
| aws | ~> 5.0 |

## Related Modules

- **api-gateway**: Consumes `user_pool_arn` for Cognito authorizer configuration
- **ecs**: Application Service validates JWTs using `jwks_url` and `client_id`

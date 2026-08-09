# ADR-003: Cognito vs Third-Party Authentication Provider

## Status

Accepted

## Date

2024-01-15

## Context

The platform requires OAuth2/OIDC authentication with user registration, login, JWT token issuance, and role-based access control. Options evaluated:

1. **Amazon Cognito** — AWS-managed identity provider
2. **Auth0** — Third-party identity-as-a-service
3. **Keycloak (self-hosted)** — Open-source identity server on ECS
4. **Firebase Auth** — Google-managed identity provider

## Decision

We chose **Amazon Cognito** user pools with OAuth2 Authorization Code + PKCE flow.

## Rationale

| Criterion | Cognito | Auth0 | Keycloak | Firebase Auth |
|-----------|---------|-------|----------|---------------|
| AWS integration | Native (IAM roles, API GW authorizer) | External (custom Lambda authorizer) | External | External |
| Cost (demo) | Free tier (50k MAU) | Free tier (7k MAU) | Compute cost (ECS task) | Free tier (phone auth limited) |
| Terraform support | First-class aws_cognito_* resources | terraform-provider-auth0 | Manual configuration | No official provider |
| LocalStack emulation | Supported | Not applicable | Docker Compose container | Not applicable |
| OIDC standard | Full compliance | Full compliance | Full compliance | Partial |
| Custom claims | Via pre-token-generation Lambda | Dashboard/rules | Admin console | Custom claims API |
| Portfolio relevance | Demonstrates AWS-native auth | Shows multi-vendor integration | Shows container skills | Less relevant to AWS SA |

Cognito was selected because:

- **Zero cost** within free tier for the demo usage pattern (Requirement 14.7)
- **Native API Gateway integration** via Cognito authorizer eliminates custom Lambda authorizer code
- **IAM role mapping** from Cognito groups enables the role-based access control model (Requirement 5.3)
- **Terraform first-class support** allows full IaC definition of user pools, clients, and groups
- **LocalStack emulation** enables local development without AWS costs (Requirement 13.2)
- **SA portfolio positioning** — demonstrates deep AWS service integration expected in AWS-focused SA roles

## Consequences

- Vendor lock-in to AWS Cognito — acceptable for AWS-focused portfolio project
- Limited UI customisation for hosted login pages (mitigated by API-only usage in this project)
- Pre-token-generation Lambda required for custom claims in JWT (adds Lambda infrastructure)
- Cognito pricing becomes significant at scale (>50k MAU) — documented in cost analysis but not relevant for demo

## Alternatives Considered

- **Auth0**: Superior developer experience and UI customisation, but adds external dependency and reduces AWS-native demonstration value
- **Keycloak**: Full control and customisability, but adds operational overhead (another ECS task, database, upgrades) disproportionate to the auth requirement
- **Firebase Auth**: Cross-platform but poor AWS integration and limited Terraform support

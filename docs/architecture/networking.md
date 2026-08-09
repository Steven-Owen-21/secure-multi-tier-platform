# Network Architecture

## VPC Topology

The platform deploys within a single VPC (`10.0.0.0/16`) in eu-west-2 with public and private subnets across two Availability Zones. Network isolation is enforced through subnet placement, route tables, NACLs, and security groups.

### VPC Layout

```mermaid
graph TB
    subgraph VPC["VPC 10.0.0.0/16 (eu-west-2)"]
        IGW[Internet Gateway]
        
        subgraph AZa["Availability Zone A (eu-west-2a)"]
            PubA["Public Subnet<br/>10.0.1.0/24"]
            PrivA["Private Subnet<br/>10.0.10.0/24"]
            NAT_A[NAT Gateway + EIP]
        end
        
        subgraph AZb["Availability Zone B (eu-west-2b)"]
            PubB["Public Subnet<br/>10.0.2.0/24"]
            PrivB["Private Subnet<br/>10.0.11.0/24"]
            NAT_B[NAT Gateway + EIP]
        end

        subgraph Endpoints["VPC Endpoints"]
            S3EP[S3 Gateway Endpoint]
            DDBEP[DynamoDB Gateway Endpoint]
            CWEndpoint[CloudWatch Logs<br/>Interface Endpoint]
            SMEndpoint[Secrets Manager<br/>Interface Endpoint]
            ECREndpoint[ECR API + DKR<br/>Interface Endpoints]
        end
    end

    Internet((Internet)) --> IGW
    IGW --> PubA & PubB
    NAT_A --> PubA
    NAT_B --> PubB
    PrivA -->|Outbound via| NAT_A
    PrivB -->|Outbound via| NAT_B
    PrivA & PrivB --> S3EP & DDBEP
    PrivA & PrivB --> CWEndpoint & SMEndpoint & ECREndpoint
```

### Subnet Allocation

| Subnet | CIDR | AZ | Purpose | Resources |
|--------|------|-----|---------|-----------|
| Public A | 10.0.1.0/24 | eu-west-2a | Internet-facing | ALB, NAT Gateway |
| Public B | 10.0.2.0/24 | eu-west-2b | Internet-facing | ALB, NAT Gateway |
| Private A | 10.0.10.0/24 | eu-west-2a | Application + Data | ECS tasks, Aurora, Redis |
| Private B | 10.0.11.0/24 | eu-west-2b | Application + Data | ECS tasks, Aurora, Redis |

### Route Tables

```mermaid
graph LR
    subgraph PublicRT["Public Route Table (per subnet)"]
        R1["0.0.0.0/0 → Internet Gateway"]
        R2["10.0.0.0/16 → local"]
    end
    
    subgraph PrivateRTa["Private Route Table (AZ-a)"]
        R3["0.0.0.0/0 → NAT Gateway (AZ-a)"]
        R4["10.0.0.0/16 → local"]
        R5["s3 prefix list → S3 Gateway Endpoint"]
        R6["dynamodb prefix list → DDB Gateway Endpoint"]
    end

    subgraph PrivateRTb["Private Route Table (AZ-b)"]
        R7["0.0.0.0/0 → NAT Gateway (AZ-b)"]
        R8["10.0.0.0/16 → local"]
        R9["s3 prefix list → S3 Gateway Endpoint"]
        R10["dynamodb prefix list → DDB Gateway Endpoint"]
    end
```

### Network Access Control Lists (NACLs)

#### Public Subnet NACLs

| Rule # | Direction | Protocol | Port Range | Source/Dest | Action |
|--------|-----------|----------|------------|-------------|--------|
| 100 | Inbound | TCP | 443 | 0.0.0.0/0 | ALLOW |
| 110 | Inbound | TCP | 1024-65535 | 0.0.0.0/0 | ALLOW |
| * | Inbound | All | All | 0.0.0.0/0 | DENY |
| 100 | Outbound | TCP | All | 0.0.0.0/0 | ALLOW |
| * | Outbound | All | All | 0.0.0.0/0 | DENY |

#### Private Subnet NACLs

| Rule # | Direction | Protocol | Port Range | Source/Dest | Action |
|--------|-----------|----------|------------|-------------|--------|
| 100 | Inbound | All | All | 10.0.0.0/16 | ALLOW |
| * | Inbound | All | All | 0.0.0.0/0 | DENY |
| 100 | Outbound | All | All | 10.0.0.0/16 | ALLOW |
| 110 | Outbound | TCP | 443 | 0.0.0.0/0 | ALLOW |
| * | Outbound | All | All | 0.0.0.0/0 | DENY |

### VPC Endpoints

Private connectivity to AWS services without traversing the public internet:

| Endpoint | Type | Purpose | Cost Benefit |
|----------|------|---------|-------------|
| S3 | Gateway | Bucket access (logs, assets, backups) | Free, no NAT charges |
| DynamoDB | Gateway | Terraform state locking | Free, no NAT charges |
| CloudWatch Logs | Interface | Log delivery from ECS tasks | Reduced NAT traffic |
| Secrets Manager | Interface | Credential retrieval | Reduced NAT traffic |
| ECR API | Interface | Container image pulls | Reduced NAT traffic |
| ECR DKR | Interface | Docker layer downloads | Reduced NAT traffic |

### VPC Flow Logs

- **Capture**: All traffic (ACCEPT and REJECT)
- **Destination**: CloudWatch Logs group
- **Retention**: 30 days
- **Purpose**: Network forensics, troubleshooting, compliance auditing

### DNS Configuration

- `enableDnsHostnames`: true (required for VPC endpoints)
- `enableDnsSupport`: true (required for Route 53 private hosted zones)
- Interface endpoints use private DNS for seamless service access

### Traffic Flow Patterns

```mermaid
sequenceDiagram
    participant Internet
    participant IGW as Internet Gateway
    participant ALB as ALB (Public)
    participant ECS as ECS Task (Private)
    participant Aurora as Aurora (Private)
    participant S3EP as S3 Endpoint

    Note over Internet,S3EP: Inbound API Request
    Internet->>IGW: HTTPS request
    IGW->>ALB: Route to ALB
    ALB->>ECS: Forward to healthy target
    ECS->>Aurora: Database query (within VPC)
    
    Note over Internet,S3EP: Outbound via NAT
    ECS->>IGW: External API call via NAT GW
    
    Note over Internet,S3EP: Private AWS Access
    ECS->>S3EP: S3 access via gateway endpoint
```

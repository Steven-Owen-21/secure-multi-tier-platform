"""Generate AWS architecture diagram for the Secure Multi-Tier Platform.

Requires:
    - pip install diagrams
    - Graphviz installed and on PATH (https://graphviz.org/download/)
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.network import VPC, PublicSubnet, PrivateSubnet, NATGateway, ALB, CloudFront, Route53, APIGateway
from diagrams.aws.security import WAF, Guardduty, SecurityHub, KMS, SecretsManager, Cognito, IAM
from diagrams.aws.database import Aurora, ElastiCache
from diagrams.aws.compute import ECS, Fargate
from diagrams.aws.storage import S3
from diagrams.aws.management import Cloudwatch, Config
from diagrams.aws.integration import SNS
from diagrams.aws.general import Client

with Diagram("Secure Multi-Tier Platform", show=False, filename="docs/architecture/architecture", direction="TB", graph_attr={"fontsize": "28", "bgcolor": "white", "pad": "0.5"}):

    client = Client("API Clients")

    with Cluster("Edge Layer"):
        r53 = Route53("Route 53\nFailover")
        cf = CloudFront("CloudFront\nCDN")
        waf = WAF("AWS WAF\nManaged Rules")

    with Cluster("AWS Region (eu-west-2)"):

        with Cluster("VPC - Public Subnets"):
            alb = ALB("Application\nLoad Balancer")
            apigw = APIGateway("API Gateway\nUsage Plans")
            nat = NATGateway("NAT Gateway\n(per AZ)")

        with Cluster("VPC - Private Subnets (Application Tier)"):
            ecs = ECS("ECS Fargate\nAuto Scaling")

        with Cluster("VPC - Private Subnets (Data Tier)"):
            aurora = Aurora("Aurora PostgreSQL\nMulti-AZ")
            redis = ElastiCache("ElastiCache Redis\nFailover + TLS")
            s3 = S3("S3 Storage\nLifecycle + Tiering")

        with Cluster("Security & Identity"):
            cognito = Cognito("Cognito\nOAuth2/OIDC")
            kms = KMS("KMS CMK\nEncryption")
            secrets = SecretsManager("Secrets Manager\n30-day Rotation")
            guardduty = Guardduty("GuardDuty")
            sechub = SecurityHub("Security Hub")
            iam = IAM("IAM Advanced\nPermission Boundaries")

        with Cluster("Observability"):
            cw = Cloudwatch("CloudWatch\nComposite Alarms")
            config = Config("AWS Config\nCompliance")
            sns = SNS("SNS Alerts")

    with Cluster("DR Region (eu-west-1)"):
        aurora_dr = Aurora("Aurora Replica\nCross-Region")
        s3_dr = S3("S3 Replication")

    # Connections
    client >> r53 >> cf >> waf >> alb
    alb >> apigw >> ecs
    ecs >> aurora
    ecs >> redis
    ecs >> s3
    ecs >> cognito
    ecs >> secrets

    # Security connections
    kms >> Edge(style="dashed") >> aurora
    kms >> Edge(style="dashed") >> redis
    kms >> Edge(style="dashed") >> s3
    guardduty >> sechub
    config >> sechub
    sechub >> sns
    cw >> sns

    # NAT Gateway (private subnet outbound)
    ecs >> Edge(style="dashed", color="gray", label="Outbound via NAT") >> nat

    # DR connections
    aurora >> Edge(style="dotted", label="Async Replication") >> aurora_dr
    s3 >> Edge(style="dotted", label="CRR") >> s3_dr

"""Generate request flow diagram for Secure Multi-Tier Platform."""

import os
from diagrams import Diagram, Edge
from diagrams.onprem.client import Client
from diagrams.aws.network import Route53, CloudFront, ALB, APIGateway
from diagrams.aws.security import WAF, Cognito, SecretsManager
from diagrams.aws.compute import Fargate
from diagrams.aws.database import Aurora, ElasticacheForRedis

# Output path relative to project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
output_dir = os.path.join(project_root, "docs", "architecture")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "request-flow")

with Diagram(
    "Request Flow — Secure Multi-Tier Platform",
    filename=output_path,
    show=False,
    direction="LR",
    graph_attr={"dpi": "150", "bgcolor": "white"},
):
    client = Client("Client")
    dns = Route53("Route 53")
    cdn = CloudFront("CloudFront")
    waf = WAF("WAF")
    alb = ALB("ALB")
    apigw = APIGateway("API Gateway")
    ecs = Fargate("ECS Fargate")
    cache = ElasticacheForRedis("ElastiCache\nRedis")
    db = Aurora("Aurora\nPostgreSQL")
    cognito = Cognito("Cognito")
    secrets = SecretsManager("Secrets\nManager")

    # Main request path
    client >> dns >> cdn >> waf >> alb >> apigw >> ecs

    # Cache hit (green)
    ecs >> Edge(color="green", label="Cache Hit") >> cache

    # Cache miss → DB (orange)
    ecs >> Edge(color="orange", label="Cache Miss → DB Query") >> db

    # JWT Validation (blue)
    ecs >> Edge(color="blue", label="JWT Validation") >> cognito

    # Credentials (purple dashed)
    ecs >> Edge(color="purple", style="dashed", label="Credentials") >> secrets

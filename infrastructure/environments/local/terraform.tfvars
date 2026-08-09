# -----------------------------------------------------------------------------
# Local Development Environment
# -----------------------------------------------------------------------------
# Used with Docker Compose + LocalStack for zero-cost local development.
# Terraform is not typically applied in this environment — values exist
# for validation and local plan testing.

environment = "local"
aws_region  = "eu-west-2"

# Networking
vpc_cidr = "10.0.0.0/16"
az_count = 2

# Compute (minimised for local)
app_port         = 8000
ecs_min_capacity = 1
ecs_max_capacity = 2

# Database
db_backup_retention_days = 1

# WAF
waf_rate_limit      = 2000
waf_body_size_limit = 8192

# Tagging
owner       = "local-dev"
cost_centre = "engineering"

# -----------------------------------------------------------------------------
# Demo Environment
# -----------------------------------------------------------------------------
# On-demand AWS deployment for live demonstrations.
# Target: under £5 for a 2-hour session.
# Provisioned and destroyed via GitHub Actions demo workflow.

environment = "demo"
aws_region  = "eu-west-2"

# Networking
vpc_cidr = "10.0.0.0/16"
az_count = 2

# Compute
app_port         = 8000
ecs_min_capacity = 2
ecs_max_capacity = 10

# Database
db_backup_retention_days = 7

# WAF
waf_rate_limit      = 2000
waf_body_size_limit = 8192

# Tagging
owner       = "platform-team"
cost_centre = "engineering"

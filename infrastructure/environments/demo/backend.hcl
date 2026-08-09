# Backend configuration for the demo environment.
# Usage: terraform init -backend-config=environments/demo/backend.hcl

bucket         = "secure-multi-tier-platform-tfstate"
key            = "demo/terraform.tfstate"
region         = "eu-west-2"
dynamodb_table = "secure-multi-tier-platform-tflock"
encrypt        = true

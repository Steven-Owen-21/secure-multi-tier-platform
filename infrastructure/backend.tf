# Remote state backend for demo environment.
# Local environment uses the default local backend.
# To use remote state, initialise with:
#   terraform init -backend-config=environments/demo/backend.hcl

terraform {
  backend "s3" {
    bucket         = "secure-multi-tier-platform-tfstate"
    key            = "infrastructure/terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "secure-multi-tier-platform-tflock"
    encrypt        = true
  }
}

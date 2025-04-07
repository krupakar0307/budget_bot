terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }
  }
}
provider "aws" {
  region = "us-east-1"
}

# terraform {
#   backend "s3" {
#     bucket       = "expense-tracker-llm-s3-backend"
#     key          = "s3/terraform.tfstate"
#     encrypt      = "true"
#     use_lockfile = "true"

#   }
# }

module "s3_bucket" {
  source      = "../modules/s3-mod"
  bucket_name = var.bucket_name
  environment = var.environment
  aws_region  = var.aws_region
  tags_all    = var.tags_all
}
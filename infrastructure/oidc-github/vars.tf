variable "aws_region" {
  description = "Provide AWS Region to create resources"
  default     = "us-east-1"
  type        = string
}
variable "url" {
  description = "value of the URL"
  type        = string
  default     = "https://token.actions.githubusercontent.com"
}

variable "role_name" {
  description = "Role that is attached to OIDC"
  default     = "github_oidc_role_expensive-tracker"
  type        = string
}

variable "s3_backend_bucket" {
  type        = string
  description = "configure backend bucket for terraform state store"
  default     = "expense-tracker-llm-s3-backend"
}
variable "github_organization" {
  description = "Enter github organization name for accessing to aws"
  default     = "Debuide"
  type        = string
}

# Restricting access to resources from the OIDC created above to a specific branch in the repository.
# If the branch is not provided, it will allow access to all branches.
variable "repo" {
  description = "Enter github repo name to restrict access for specific repo"
  default     = "expense-tracker"
  type        = string
}
variable "branch" {
  description = "enter the branch name to run ci/cd actions"
  default     = ""
  type        = string
}

variable "tags_all" {
  description = "set tags"
  type        = map(string)
  default = {
    Environment = "stg"
    managed_by  = "terraform"
    terraform   = "true"
    Project     = "Expense-Tracker-LLM"
  }
}




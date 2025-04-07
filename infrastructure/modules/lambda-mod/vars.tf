variable "aws_region" {
  description = "AWS region"
  type        = string
}
variable "environment_variables" {
  description = "Environment variables for the lambda function"
  type        = map(string)
  default     = {}
}
variable "environment" {
  default     = ""
  description = "add environment"
  type        = string
}
variable "lambda_function_name" {
  description = "Name of the lambda function"
  type        = string
  default     = "your_lambda_function"
}
variable "lambda_function_file_path" {
  description = "Path to the lambda function"
  type        = string
  default     = ""
}
variable "handler" {
  description = "Handler for the lambda function"
  type        = string
  default     = "lambda_function.lambda_handler"
}
variable "runtime" {
  description = "Runtime for the lambda function"
  type        = string
  default     = "python3.12"
}
##bedrock resource arn
variable "create_bedrock_policy" {
  description = "Create bedrock policy"
  type        = bool
  default     = false
}

variable "bedrock_resource_arn" {
  description = "ARN of the bedrock resource for lambda access"
  type        = string
  default     = "*"
  validation {
    condition     = var.create_bedrock_policy == false || (var.create_bedrock_policy == true && var.bedrock_resource_arn != "")
    error_message = "If bedrock_resource_arn is true, bedrock_resource_arn must be provided."
  }
}

##S3 resource arn
variable "create_s3_policy" {
  description = "Create S3 policy"
  type        = bool
  default     = false
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 resource for lambda access"
  type        = string
  default     = ""
  validation {
    condition     = var.create_s3_policy == false || (var.create_s3_policy == true && var.s3_bucket_arn != "")
    error_message = "If create_s3_policy is true, s3_bucket_arn must be provided."
  }
}

variable "tags_all" {
  description = "set tags"
  type        = map(string)
  default = {
    Environment = ""
    managed_by  = "terraform"
    terraform   = "true"
    Project     = "Expense-Tracker-LLM"
  }
}

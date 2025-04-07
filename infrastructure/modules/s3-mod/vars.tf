variable "aws_region" {
  description = "AWS region"
  type        = string

}
variable "bucket_name" {
  description = "Name of the S3 bucket"
  type        = string
  default     = ""
}

variable "environment" {
  description = "Environment for the lambda function"
  type        = string
  default     = ""
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
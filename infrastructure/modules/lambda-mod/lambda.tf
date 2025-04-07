provider "aws" {
  region = var.aws_region
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = var.lambda_function_file_path
  output_path = "lambda_function.zip"
}

resource "aws_lambda_function" "this" {
  function_name    = "${var.lambda_function_name}-${var.environment}"
  handler          = var.handler
  runtime          = var.runtime
  role             = aws_iam_role.iam_for_lambda.arn
  filename         = "lambda_function.zip"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = var.environment_variables
  }
  logging_config {
    log_format = "Text"
  }
  depends_on = [
    aws_iam_policy.lambda_logging,
    aws_cloudwatch_log_group.this,
  ]
  tags_all = var.tags_all
}
resource "aws_lambda_function_url" "this" {
  function_name      = aws_lambda_function.this.function_name
  authorization_type = "NONE"
  invoke_mode        = "BUFFERED"
}

# IAM role for lambda
resource "aws_iam_role" "iam_for_lambda" {
  name               = "${var.lambda_function_name}-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  tags_all           = var.tags_all
}

## cloudwatch logging configuration
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.lambda_function_name}-${var.environment}"
  retention_in_days = 14
  tags_all          = var.tags_all
}

resource "aws_iam_policy" "lambda_logging" {
  name = "lambda_logging-${var.environment}"
  #   path        = "/"
  description = "IAM policy for logging from a lambda"
  policy      = data.aws_iam_policy_document.lambda_logging.json
  tags_all    = var.tags_all
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = aws_iam_policy.lambda_logging.arn
}


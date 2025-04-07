## consists of 2 policies, one is for logging and other is for invoking the model
data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "lambda_logging" {

  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["${aws_cloudwatch_log_group.this.arn}:*"]
  }
}

resource "aws_iam_role_policy_attachment" "lambda_logging" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = aws_iam_policy.lambda_logging.arn
}

resource "aws_iam_policy" "bedrock_policy" {
  count = var.create_bedrock_policy ? 1 : 0

  name = "${var.lambda_function_name}_bedrock_policy-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "bedrock:InvokeModel",
          "bedrock:ListModels",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Effect   = "Allow"
        Resource = [var.bedrock_resource_arn]
      }
    ]
  })
  tags_all = var.tags_all
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  count      = var.create_bedrock_policy ? 1 : 0
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = aws_iam_policy.bedrock_policy[count.index].arn
}

resource "aws_iam_policy" "lambda_s3_policy" {
  count = var.create_s3_policy ? 1 : 0

  name = "${var.lambda_function_name}_s3_policy-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:PutObject",
          "s3:GetObject",
        ]
        Effect   = "Allow"
        Resource = [var.s3_bucket_arn]
      }
    ]
  })
  tags_all = var.tags_all
}

resource "aws_iam_role_policy_attachment" "s3_policy_attachment" {
  count      = var.create_s3_policy ? 1 : 0
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = aws_iam_policy.lambda_s3_policy[count.index].arn
}
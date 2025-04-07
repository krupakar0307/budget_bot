data "aws_caller_identity" "current" {}
resource "aws_iam_policy" "lambda_function" {
  name        = "LambdaFunctionPolicy"
  description = "Lambda Access Policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        "Action" : [
          "lambda:CreateFunction",
          "lambda:UpdateFunctionCode",
          "lambda:UpdateFunctionConfiguration",
          "lambda:CreateFunctionUrlConfig",
          "lambda:DeleteFunctionUrlConfig",
          "lambda:UntagResource",
          "lambda:AddPermission",
          "logs:CreateLogGroup",
          "logs:Get*",
          "logs:UntagResource",
          "logs:Put*",
          "logs:List*",
          "logs:Describe*",
          "logs:Tag*",
          "cloudwatch:*",
          "lambda:Get*",
          "lambda:List*",
          "lambda:Tag*",
          "iam:Get*",
          "iam:Put*",
          "iam:List*",
          "iam:CreateRole",
          "iam:Tag*",
          "iam:UntagRole",
          "iam:UntagPolicy",
          "iam:CreatePolicy",
          "iam:AttachRolePolicy",
          "iam:PassRole"
        ],
        "Effect" : "Allow",
        "Resource" = [
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:*",
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:*",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/*",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:policy/*"
        ]
      }
    ],
  })
}
# Attaching Inline Policy to the Role to access resources
resource "aws_iam_role_policy_attachment" "eks_auth_policy_attachment" {
  role       = aws_iam_role.github_oidc_role.name
  policy_arn = aws_iam_policy.lambda_function.arn
}

# S3 bucket policy allows terraform to read/write state files and only create new S3 buckets
resource "aws_iam_policy" "s3_bucket_policy" {
  name        = "S3BucketPolicy"
  description = "allows terraform to read/write state files and only create new S3 buckets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Read/Write access to the statefile bucket
      {
        "Action" : [
          "s3:ListBucket",
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ],
        "Effect" : "Allow",
        "Resource" : [
          "arn:aws:s3:::${var.s3_backend_bucket}",
          "arn:aws:s3:::${var.s3_backend_bucket}/*" ## only to read and write terraform state in s3 backend bucket.
        ]
      },
      {
        "Action" : [
          "s3:CreateBucket",
          "s3:ListBucket",
          "s3:Get*",
          "s3:Put*"
        ],
        "Effect" : "Allow",
        "Resource" : "*"
      }
    ]
  })
  tags_all = var.tags_all
}

resource "aws_iam_role_policy_attachment" "s3_bucket_policy_attachment" {
  role       = aws_iam_role.github_oidc_role.name
  policy_arn = aws_iam_policy.s3_bucket_policy.arn
}
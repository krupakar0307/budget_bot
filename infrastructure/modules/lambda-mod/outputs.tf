output "name" {
  value = aws_lambda_function.this.function_name
}
output "aws_lambda_function_url" {
  value = aws_lambda_function_url.this.function_url
}
output "aws_iam_role" {
  value = aws_iam_role.iam_for_lambda.arn
}

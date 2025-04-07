output "role_arn" {
  description = "value of the role arn created"
  value       = aws_iam_role.github_oidc_role.arn
}
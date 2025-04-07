## OIDC for GitHub

This terraform code is used to create a github provider in aws-iam.

- configured backend for statefile store.
- this will create oidc provider along with iam-role and policy attached.
- currently limited permissions are set to this provider - Lambda and S3

## setup

- perform terraform actions from local, set aws-configure.
- cd into `oidc-github` folder, initialize terraform. - `terraform init`
- validate the plan and apply - `terraform apply`

In future if required to add further policies, add it  `iam.tf` file
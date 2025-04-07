## Lamba Module

This module is to create lambda in aws. 

- this will create necessary iam roles, cloudwatch logs to the function.
- module takes care of zipping the file, just need to provide the correct path for the code folder.
- currently this will create policy for s3 and bedrock based on bool flags.


## usage

```
module "lambda" {
    aws_region                = var.aws_region
    environment               = var.environment
    source                    = "../modules/lambda-mod"
    lambda_function_file_path = "${path.module}/../../service" ## provide correct path to the code.
    lambda_function_name      = "lambda_function"
    handler                   = "lambda_function.lambda_handler" ## replace with correct handler
    runtime                   = "python3.12" ## replace with required version
    create_bedrock_policy     = false # set to true if needs to create bedrock-policy
    create_s3_policy          = false # set to true if needs to create s3
    environment_variables = {
        "BEDROCK_RESOURCE_ARN" = var.bedrock_resource_arn
        "S3_RESOURCE_ARN" = var.s3_resource_arn
    } ## environment variables to set if any.
}

```

`create_bedock_policy` if this sets to true, then `bedrock_resource_arn` value need to set, to restrict the policy for this lambda only to that particular bedrock-llm.

Similarly for `create_s3_policy`, required to pass `s3_resource_arn` value.


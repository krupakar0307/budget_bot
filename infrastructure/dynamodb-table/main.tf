provider "aws" {
  region = "us-east-1" # Change this to your region
}

resource "aws_dynamodb_table" "processed_messages" {
  name         = "ProcessedMessages-1"
  billing_mode = "PAY_PER_REQUEST"

  hash_key     = "message_id"

  attribute {
    name = "message_id"
    type = "S"
  }

  attribute {
    name = "username"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  global_secondary_index {
    name            = "username-timestamp-index"
    hash_key        = "username"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  tags = {
    Environment = "dev"
    Project     = "Messaging"
  }
}

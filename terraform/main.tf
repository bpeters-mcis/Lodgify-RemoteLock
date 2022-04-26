###############
# IAM Assets
###############
# Create the lambda role
resource "aws_iam_role" "this" {
  name               = "${var.lambda_function_name}_role"
  path               = "/"
  assume_role_policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": "sts:AssumeRole",
            "Principal": {
               "Service": "lambda.amazonaws.com"
            },
            "Effect": "Allow",
            "Sid": ""
        }
    ]
}
EOF
}

# Create policy to allow access to all lambdarama parameter store values
resource "aws_iam_role_policy" "this" {
  name   = "${var.lambda_function_name}_policy"
  role   = aws_iam_role.this.id
  policy = <<POLICY
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "WriteLogs",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogStream",
                "logs:CreateLogGroup",
                "logs:PutLogEvents"
            ],
            "Resource": [
              "arn:aws:logs:*:*:log-group:/aws/lambda/${var.lambda_function_name}",
              "arn:aws:logs:*:*:log-group:/aws/lambda/${var.lambda_function_name}:log-stream:*"
            ]
        },
        {
            "Sid": "SendEmail",
            "Effect": "Allow",
            "Action": [
                "ses:*"
            ],
            "Resource": "*"
        },
    ]
  }
POLICY
}

###############
# Lambda Function Assets
###############

# Create zip file of the source code
data "archive_file" "this" {
  type        = "zip"
  source_file = "../lambda_code/*"
  output_path = "../zip_files/lambda.zip"
}

# Create lambda function
resource "aws_lambda_function" "this" {
  filename         = "../zip_files/lambda.zip"
  function_name    = var.lambda_function_name
  role             = aws_iam_role.this.arn
  handler          = "guest_hander.handler"
  runtime          = "python3.9"
  memory_size      = var.lambda_memory_size
  timeout          = var.lambda_execution_timeout
  source_code_hash = data.archive_file.this.output_base64sha256
  environment {

  }
}

################
# Cloudwatch Assets
################

# Cloudwatch rule to run this lambda
resource "aws_cloudwatch_event_rule" "this" {
  name                = var.lambda_function_name
  description         = "Run automation on set schedule"
  schedule_expression = var.lambda_execution_rule_expression
  is_enabled          = true
}

# Create cloudwatch trigger
resource "aws_cloudwatch_event_target" "target" {
  rule      = aws_cloudwatch_event_rule.this.name
  target_id = var.lambda_function_name
  arn       = aws_lambda_function.this.arn
}

# Allow cloudwatch to invoke this function
resource "aws_lambda_permission" "cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.this.arn
}

# Create log group for this function, with our set retention period
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = var.cloudwatch_log_retention_in_days
}
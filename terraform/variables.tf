variable "lambda_execution_rule_expression" {
  type        = string
  description = "The rate expression to run the lambda, ex: 'rate(1 days)'"
  default = "rate(1 days)"
}

variable "lambda_function_name" {
  type        = string
  description = "Name of the lambda function"
  default = "LodgifyLockAutomation"
}

variable "lambda_memory_size" {
  type        = number
  default     = 512
  description = "Memory size in MB for lambdas in this project"
}

variable "lambda_execution_timeout" {
  type        = number
  default     = 120
  description = "Timeout in seconds for the lambda functions"
}

variable "cloudwatch_log_retention_in_days" {
  type        = number
  default     = 14
  description = "Days to keep logs in cloudwatch"
}
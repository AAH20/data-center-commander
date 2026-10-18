terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# IAM Access Analyzer
resource "aws_accessanalyzer_analyzer" "this" {
  analyzer_name = var.analyzer_name
  type          = var.analyzer_type

  tags = var.tags
}

# IAM Access Analyzer - Unused Access (Account-level only)
resource "aws_accessanalyzer_analyzer" "unused_access" {
  count = var.unused_access_enabled && var.analyzer_type == "ACCOUNT" ? 1 : 0

  analyzer_name = "${var.analyzer_name}-unused-access"
  type          = "ACCOUNT_UNUSED_ACCESS"

  tags = var.tags
}

# IAM Access Analyzer Rules
resource "aws_accessanalyzer_archive_rule" "this" {
  for_each = { for rule in var.rules : rule.name => rule }

  analyzer_name = aws_accessanalyzer_analyzer.this.analyzer_name
  rule_name     = each.value.name

  dynamic "filter" {
    for_each = each.value.details
    content {
      contains = lookup(filter.value, "contains", null)
      eq       = lookup(filter.value, "eq", null)
      exists   = lookup(filter.value, "exists", null)
      neq      = lookup(filter.value, "neq", null)
    }
  }
}

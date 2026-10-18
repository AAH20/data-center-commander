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

# Security Hub
resource "aws_securityhub_account" "this" {
  count = var.enable_security_hub ? 1 : 0

  enable_default_standards  = false
  control_finding_generator = var.control_finding_generator
  auto_enable_new_standards = var.auto_enable_new_standards
}

# Security Hub Standards
resource "aws_securityhub_standards_subscription" "this" {
  for_each = { for std in var.enable_standards : std.name => std }

  standards_arn = "arn:aws:securityhub:${data.aws_region.current.name}::standard/${each.value.name}${each.value.version != null ? "/${each.value.version}" : ""}"

  depends_on = [aws_securityhub_account.this]
}

# Security Hub Member Invitations
resource "aws_securityhub_member" "this" {
  for_each = { for member in var.members : member.account_id => member }

  master_id  = data.aws_caller_identity.current.account_id
  account_id = each.value.account_id
  email      = each.value.email
  invite     = each.value.invite

  depends_on = [aws_securityhub_account.this]
}

# Security Hub Product Integrations
resource "aws_securityhub_product_subscription" "this" {
  for_each = toset(var.product_integrations)

  product_arn = "arn:aws:securityhub:${data.aws_region.current.name}::product/${each.value}"

  depends_on = [aws_securityhub_account.this]
}

# Security Hub Action Target
resource "aws_securityhub_action_target" "this" {
  count = var.enable_security_hub ? 1 : 0

  name        = var.action_target_name
  description = var.action_target_description
  identifier  = var.action_target_name

  depends_on = [aws_securityhub_account.this]
}

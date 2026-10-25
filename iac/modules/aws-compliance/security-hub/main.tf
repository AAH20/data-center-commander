terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# `aws_caller_identity.current` is not wired into `aws_securityhub_member`:
# the provider derives the inviting account from the caller identity and
# exposes it as the computed `master_id`, which cannot be configured.

# Security Hub
resource "aws_securityhub_account" "this" {
  count = var.enable_security_hub ? 1 : 0

  enable_default_standards  = false
  control_finding_generator = var.control_finding_generator

  # `aws_securityhub_account` has no `auto_enable_new_standards` argument.
  # The per-account setting the API exposes is `auto_enable_controls`: new
  # controls added to standards that are already subscribed are enabled
  # automatically. Auto-enabling *new standards* is an Organizations-level
  # setting (`aws_securityhub_organization_configuration.auto_enable_standards`)
  # and is not available per account; this module subscribes standards
  # explicitly in `aws_securityhub_standards_subscription` instead.
  auto_enable_controls = var.auto_enable_controls
}

# Security Hub Standards
resource "aws_securityhub_standards_subscription" "this" {
  for_each = { for std in var.enable_standards : std.name => std }

  standards_arn = "arn:aws:securityhub:${data.aws_region.current.region}::standard/${each.value.name}${each.value.version != null ? "/${each.value.version}" : ""}"

  depends_on = [aws_securityhub_account.this]
}

# Security Hub Member Invitations
resource "aws_securityhub_member" "this" {
  for_each = { for member in var.members : member.account_id => member }

  # `master_id` is computed-only in the AWS provider (the inviting account is
  # taken from the caller identity), so it cannot be configured here.
  account_id = each.value.account_id
  email      = each.value.email
  invite     = each.value.invite

  depends_on = [aws_securityhub_account.this]
}

# Security Hub Product Integrations
resource "aws_securityhub_product_subscription" "this" {
  for_each = toset(var.product_integrations)

  product_arn = "arn:aws:securityhub:${data.aws_region.current.region}::product/${each.value}"

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

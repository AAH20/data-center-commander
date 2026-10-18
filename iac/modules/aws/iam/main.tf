terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_iam_role" "this" {
  for_each = var.roles

  name                 = each.key
  description          = each.value.description
  assume_role_policy   = each.value.assume_role_policy
  max_session_duration = each.value.max_session_duration
  permissions_boundary = each.value.permissions_boundary
  managed_policy_arns  = each.value.managed_policy_arns

  dynamic "inline_policy" {
    for_each = each.value.inline_policies
    content {
      name   = inline_policy.value.name
      policy = inline_policy.value.policy
    }
  }

  tags = merge(var.tags, {
    Name = each.key
  })
}

resource "aws_iam_policy" "this" {
  for_each = var.policies

  name        = each.key
  description = each.value.description
  policy      = each.value.policy

  tags = merge(var.tags, {
    Name = each.key
  })
}

resource "aws_iam_instance_profile" "this" {
  for_each = var.instance_profiles

  name = each.key
  role = each.value.role_name

  tags = merge(var.tags, {
    Name = each.key
  })
}

resource "aws_iam_group" "this" {
  for_each = var.groups

  name = each.key
}

resource "aws_iam_group_policy_attachment" "this" {
  for_each = { for k, v in var.group_policy_attachments : k => v }

  group      = each.value.group_name
  policy_arn = each.value.policy_arn
}

resource "aws_iam_user" "this" {
  for_each = var.users

  name = each.key
  path = each.value.path

  tags = merge(var.tags, {
    Name = each.key
  })
}

resource "aws_iam_user_policy_attachment" "this" {
  for_each = { for k, v in var.user_policy_attachments : k => v }

  user       = each.value.user_name
  policy_arn = each.value.policy_arn
}

resource "aws_iam_access_key" "this" {
  for_each = { for k, v in var.users : k => v if v.create_access_key }

  user = each.key
}

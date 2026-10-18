terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ─── Backup Vault ─────────────────────────────────────────────────────────────

resource "aws_backup_vault" "this" {
  name       = var.vault_name
  kms_key_id = var.kms_key_id
  tags       = merge(var.tags, { Name = var.vault_name })
}

resource "aws_backup_vault_lock_configuration" "this" {
  count               = var.enable_vault_lock ? 1 : 0
  backup_vault_name   = aws_backup_vault.this.name
  min_retention_days  = var.vault_lock_min_retention_days
  max_retention_days  = var.vault_lock_max_retention_days
  changeable_for_days = var.vault_lock_changeable_for_days
}

# ─── Backup Plan ──────────────────────────────────────────────────────────────

resource "aws_backup_plan" "this" {
  name = var.plan_name
  tags = merge(var.tags, { Name = var.plan_name })

  dynamic "rule" {
    for_each = var.backup_rules
    content {
      rule_name         = rule.value.rule_name
      target_vault_name = aws_backup_vault.this.name
      schedule          = rule.value.schedule

      lifecycle {
        cold_storage_after = rule.value.cold_storage_after
        delete_after       = rule.value.delete_after
      }

      dynamic "copy_action" {
        for_each = rule.value.copy_actions
        content {
          destination_vault_arn = copy_action.value.destination_vault_arn

          lifecycle {
            cold_storage_after = copy_action.value.cold_storage_after
            delete_after       = copy_action.value.delete_after
          }
        }
      }

      recovery_point_tags = merge(var.tags, {
        BackupType = rule.value.rule_name
      })
    }
  }

  advanced_backup_setting {
    resource_type = "EC2"
    backup_options = {
      WindowsVSS = var.enable_vss ? "enabled" : "disabled"
    }
  }
}

# ─── Backup Selection ─────────────────────────────────────────────────────────

resource "aws_backup_selection" "this" {
  for_each = var.backup_selections

  plan_id      = aws_backup_plan.this.id
  name         = each.key
  iam_role_arn = each.value.iam_role_arn

  resources = each.value.resources

  dynamic "selection_tag" {
    for_each = each.value.selection_tags
    content {
      type  = selection_tag.value.type
      key   = selection_tag.value.key
      value = selection_tag.value.value
    }
  }

  condition {
    string_equals {
      key   = "aws:ResourceTag/CreatedBy"
      value = "backup-automation"
    }
  }
}

# ─── Cross-Region Copy ────────────────────────────────────────────────────────

resource "aws_backup_plan" "cross_region" {
  count = var.cross_region_backup_enabled ? 1 : 0

  name = "${var.plan_name}-cross-region"
  tags = merge(var.tags, { Name = "${var.plan_name}-cross-region" })

  dynamic "rule" {
    for_each = var.backup_rules
    content {
      rule_name         = rule.value.rule_name
      target_vault_name = aws_backup_vault.this.name
      schedule          = rule.value.schedule

      lifecycle {
        cold_storage_after = rule.value.cold_storage_after
        delete_after       = rule.value.delete_after
      }

      copy_action {
        destination_vault_arn = var.cross_region_backup_vault_arn

        lifecycle {
          cold_storage_after = rule.value.cold_storage_after
          delete_after       = rule.value.delete_after
        }
      }
    }
  }
}

# ─── SNS Notifications ────────────────────────────────────────────────────────

resource "aws_sns_topic" "backup_notifications" {
  count = var.sns_topic_name != null ? 1 : 0

  name              = var.sns_topic_name
  kms_master_key_id = var.sns_kms_key_id
  tags              = merge(var.tags, { Name = var.sns_topic_name })
}

resource "aws_sns_topic_subscription" "email" {
  for_each = var.sns_email_endpoints

  topic_arn = aws_sns_topic.backup_notifications[0].arn
  protocol  = "email"
  endpoint  = each.value
}

resource "aws_backup_vault_notifications" "this" {
  count = var.sns_topic_name != null ? 1 : 0

  backup_vault_name   = aws_backup_vault.this.name
  sns_topic_arn       = aws_sns_topic.backup_notifications[0].arn
  backup_vault_events = var.backup_vault_events
}

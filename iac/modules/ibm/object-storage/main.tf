terraform {
  required_version = ">= 1.5.0"
  required_providers {
    ibm = {
      source  = "IBM-Cloud/ibm"
      version = "~> 1.65"
    }
  }
}

resource "ibm_cos_bucket" "this" {
  bucket_name       = var.bucket_name
  resource_group_id = var.resource_group_id
  location          = var.location
  storage_class     = var.storage_class

  dynamic "activity_tracking" {
    for_each = var.enable_activity_tracking ? [1] : []
    content {
      activity_tracker_crn = var.activity_tracker_crn
    }
  }

  dynamic "metrics_monitoring" {
    for_each = var.enable_metrics_monitoring ? [1] : []
    content {
      metrics_monitoring_crn  = var.metrics_monitoring_crn
      usage_metrics_enabled   = true
      request_metrics_enabled = true
    }
  }

  dynamic "key_protect" {
    for_each = var.encryption_key_crn != null ? [1] : []
    content {
      kms_key_crn = var.encryption_key_crn
    }
  }

  dynamic "allowed_ip" {
    for_each = var.allowed_ips
    content {
      ip = allowed_ip.value
    }
  }

  tags = var.tags
}

resource "ibm_cos_bucket_versioning" "this" {
  count = var.enable_versioning ? 1 : 0

  bucket_crn      = ibm_cos_bucket.this.crn
  bucket_location = var.location
  versioning      = "Enabled"
}

resource "ibm_cos_bucket_lifecycle_configuration" "this" {
  count = var.lifecycle_rules != null ? 1 : 0

  bucket_crn      = ibm_cos_bucket.this.crn
  bucket_location = var.location

  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_rules
    content {
      id     = lifecycle_rule.value.id
      status = lifecycle_rule.value.enabled ? "Enabled" : "Disabled"

      filter {
        prefix = lifecycle_rule.value.filter_prefix
      }

      expiration {
        days = lifecycle_rule.value.expiration_days
      }

      transition {
        days          = lifecycle_rule.value.transition_days
        storage_class = lifecycle_rule.value.transition_storage_class
      }
    }
  }
}

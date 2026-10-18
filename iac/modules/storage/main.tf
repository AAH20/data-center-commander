# =============================================================================
# Cross-Cloud Storage Abstraction Module
# =============================================================================
# Provides a unified interface for object storage across cloud providers.
# Each provider's storage is independently configured.
# =============================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

###############################################################################
# AWS S3
###############################################################################

resource "aws_s3_bucket" "this" {
  count  = var.enable_aws ? 1 : 0
  bucket = "${var.bucket_name}-aws-${var.environment}"

  tags = var.common_tags
}

resource "aws_s3_bucket_versioning" "this" {
  count  = var.enable_aws ? 1 : 0
  bucket = aws_s3_bucket.this[0].id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  count  = var.enable_aws && var.enable_encryption ? 1 : 0
  bucket = aws_s3_bucket.this[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  count  = var.enable_aws ? 1 : 0
  bucket = aws_s3_bucket.this[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

###############################################################################
# GCP Cloud Storage
###############################################################################

resource "google_storage_bucket" "this" {
  count         = var.enable_gcp ? 1 : 0
  name          = "${var.bucket_name}-gcp-${var.environment}"
  location      = var.gcp_location
  storage_class = var.storage_class

  uniform_bucket_level_access = true

  versioning {
    enabled = var.enable_versioning
  }

  dynamic "encryption" {
    for_each = var.enable_encryption && var.gcp_kms_key != "" ? [1] : []
    content {
      default_kms_key_name = var.gcp_kms_key
    }
  }

  labels = var.common_tags
}

###############################################################################
# Azure Blob Storage
###############################################################################

resource "azurerm_storage_account" "this" {
  count                    = var.enable_azure ? 1 : 0
  name                     = replace("${var.bucket_name}${var.environment}", "-", "")
  resource_group_name      = var.azure_resource_group
  location                 = var.azure_location
  account_tier             = "Standard"
  account_replication_type = var.azure_replication_type
  min_tls_version          = "TLS1_2"

  blob_properties {
    versioning_enabled = var.enable_versioning
  }

  tags = var.common_tags
}

resource "azurerm_storage_container" "this" {
  count                 = var.enable_azure ? 1 : 0
  name                  = "${var.bucket_name}-container"
  storage_account_name  = azurerm_storage_account.this[0].name
  container_access_type = "private"
}

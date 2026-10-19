# =============================================================================
# Storage — FSx for Lustre as the shared rollout / checkpoint filesystem
# =============================================================================
# Agentic RL is I/O-shaped in a way ordinary training is not: every concurrent
# agent writes a trajectory shard, and the trainer re-reads all of them each
# policy step. Local NVMe is per-node, so a shared parallel filesystem is what
# keeps rollout collection from serialising behind checkpoint writes.
#
# SCRATCH_2 provisions roughly 1,000 MB/s of throughput per TiB of capacity,
# so capacity is a throughput dial as much as a space one: 12 TiB ~= 12 GB/s.

resource "aws_fsx_lustre_file_system" "gpu" {
  count = var.enable_fsx_lustre ? 1 : 0

  storage_capacity            = var.lustre_storage_capacity_gib
  subnet_ids                  = [aws_subnet.efa.id]
  security_group_ids          = [aws_security_group.gpu.id]
  deployment_type             = var.lustre_deployment_type
  per_unit_storage_throughput = var.lustre_deployment_type == "PERSISTENT_2" ? 250 : null
  kms_key_id                  = var.kms_key_arn != "" ? var.kms_key_arn : null
  storage_type                = "SSD"
  # No FS-level auto_import_policy: the data repository association below owns
  # import/export policy for this filesystem. Setting both creates two
  # competing import rules against the same bucket.
  backup_id = null

  log_configuration {
    level = "WARN_ERROR"
  }

  tags = { Name = "${var.name_prefix}-lustre" }

  # Prevent an accidental destroy from taking the rollout corpus with it.
  lifecycle {
    prevent_destroy = true
  }
}

# ---------------------------------------------------------------------------
# Data repository association — a SEPARATE resource, not a nested block
# ---------------------------------------------------------------------------
# `data_repository_association` is not valid inside aws_fsx_lustre_file_system;
# terraform validate rejects it with "Blocks of type
# \"data_repository_association\" are not expected here." The AWS provider exposes
# it as its own resource, aws_fsx_data_repository_association, and the
# auto_export/auto_import policies nest under an `s3` block there.
#
# The link to the rollout-archive bucket is what lets trajectory shards outlive
# the filesystem -- without it, replacing the FS loses the corpus.

resource "aws_fsx_data_repository_association" "rollouts" {
  count = var.enable_fsx_lustre ? 1 : 0

  file_system_id       = aws_fsx_lustre_file_system.gpu[0].id
  data_repository_path = "s3://${aws_s3_bucket.rollout_archive.id}/lustre/"
  file_system_path     = "/rollouts"

  s3 {
    auto_export_policy {
      events = ["NEW", "CHANGED", "DELETED"]
    }

    auto_import_policy {
      events = ["NEW", "CHANGED", "DELETED"]
    }
  }

  tags = { Name = "${var.name_prefix}-rollout-dra" }
}

# ---------------------------------------------------------------------------
# Durable artifact store
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "rollout_archive" {
  bucket = "${var.name_prefix}-rollout-archive-${data.aws_caller_identity.current.account_id}"

  tags = { Name = "${var.name_prefix}-rollout-archive" }
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket_versioning" "rollout_archive" {
  bucket = aws_s3_bucket.rollout_archive.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "rollout_archive" {
  bucket = aws_s3_bucket.rollout_archive.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.kms_key_arn != "" ? "aws:kms" : "AES256"
      kms_master_key_id = var.kms_key_arn != "" ? var.kms_key_arn : null
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "rollout_archive" {
  bucket = aws_s3_bucket.rollout_archive.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Trajectories are large and disposable once the policy has consumed them;
# lifecycle off to cheaper storage rather than deleting outright, so a
# regression can still be reproduced from the original rollouts.
resource "aws_s3_bucket_lifecycle_configuration" "rollout_archive" {
  bucket = aws_s3_bucket.rollout_archive.id

  rule {
    id     = "trajectory-tiering"
    status = "Enabled"

    filter {
      prefix = "lustre/"
    }

    transition {
      days          = 30
      storage_class = "INTELLIGENT_TIERING"
    }

    transition {
      days          = 180
      storage_class = "GLACIER_IR"
    }

    expiration {
      days = 730
    }
  }
}

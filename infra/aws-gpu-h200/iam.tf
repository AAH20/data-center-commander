# =============================================================================
# IAM — least-privilege roles
# =============================================================================

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }

    # Confused-deputy guard: only EC2 in THIS account may assume the role.
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

# ---------------------------------------------------------------------------
# GPU node role
# ---------------------------------------------------------------------------
# Scope is deliberately narrow: read the rollout archive, write checkpoints,
# read model weights, emit metrics. No S3 wildcard, no CreateBucket, no IAM.

resource "aws_iam_role" "gpu_node" {
  name               = "${var.name_prefix}-node-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json

  tags = { Name = "${var.name_prefix}-node-role" }
}

data "aws_iam_policy_document" "gpu_node" {
  statement {
    sid    = "RolloutArchiveReadWrite"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]

    resources = [
      aws_s3_bucket.rollout_archive.arn,
      "${aws_s3_bucket.rollout_archive.arn}/*",
    ]
  }

  statement {
    sid    = "ReadModelWeights"
    effect = "Allow"

    actions = ["s3:GetObject", "s3:ListBucket"]

    resources = [
      "arn:aws:s3:::${var.name_prefix}-model-weights",
      "arn:aws:s3:::${var.name_prefix}-model-weights/*",
    ]
  }

  statement {
    sid       = "EmitMetrics"
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    # Metrics are a write-only sink; scope it to this namespace so the node
    # cannot pollute unrelated dashboards.
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["DCC/GPUCluster"]
    }
  }

  statement {
    sid    = "EcrPull"
    effect = "Allow"

    actions = [
      "ecr:GetAuthorizationToken",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "gpu_node" {
  name   = "${var.name_prefix}-node-policy"
  role   = aws_iam_role.gpu_node.id
  policy = data.aws_iam_policy_document.gpu_node.json
}

resource "aws_iam_instance_profile" "gpu_node" {
  name = "${var.name_prefix}-node-profile"
  role = aws_iam_role.gpu_node.name
}

# ---------------------------------------------------------------------------
# VPC Flow Logs role
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "flow_log_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["vpc-flow-logs.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "flow_log" {
  name               = "${var.name_prefix}-flow-log-role"
  assume_role_policy = data.aws_iam_policy_document.flow_log_assume.json

  tags = { Name = "${var.name_prefix}-flow-log-role" }
}

data "aws_iam_policy_document" "flow_log" {
  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogGroups",
      "logs:DescribeLogStreams",
    ]

    resources = ["${aws_cloudwatch_log_group.flow_log.arn}:*"]
  }
}

resource "aws_iam_role_policy" "flow_log" {
  name   = "${var.name_prefix}-flow-log-policy"
  role   = aws_iam_role.flow_log.id
  policy = data.aws_iam_policy_document.flow_log.json
}

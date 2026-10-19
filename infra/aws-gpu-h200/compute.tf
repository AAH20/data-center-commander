# =============================================================================
# Compute — 8x H200 nodes with the full 32-card EFA fabric
# =============================================================================

locals {
  # AWS's documented maximum-bandwidth layout for p5.48xlarge / p5e.48xlarge:
  #   card 0, device 0  -> ENA      (primary; cannot be EFA-only)
  #   card 0, device 1  -> EFA-only
  #   cards 1..31, device 0 -> EFA-only
  # Result: 32 EFA devices + 1 ENA device, up to 3,200 Gbps aggregate with
  # 800 Gbps available to IP traffic (EFA and IP share the same hardware).
  efa_interfaces = concat(
    [{ card = 0, device = 0, type = "interface" }],
    [{ card = 0, device = 1, type = "efa-only" }],
    [for c in range(1, var.network_card_count) : { card = c, device = 0, type = "efa-only" }],
  )
}

data "aws_ami" "dlami" {
  count = var.ami_id == "" ? 1 : 0

  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Deep Learning AMI GPU H200*"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

resource "aws_launch_template" "gpu" {
  name_prefix   = "${var.name_prefix}-"
  image_id      = var.ami_id != "" ? var.ami_id : data.aws_ami.dlami[0].id
  instance_type = var.instance_type

  # The AMI already carries NVIDIA drivers; this installs the EFA user-space
  # stack and enables RDMA. Without it NCCL silently falls back to TCP and
  # multi-node collectives collapse to ~1/10th throughput.
  user_data = base64encode(templatefile("${path.module}/templates/bootstrap.sh.tftpl", {
    enable_fsx     = var.enable_fsx_lustre
    fsx_dns_name   = var.enable_fsx_lustre ? aws_fsx_lustre_file_system.gpu[0].dns_name : ""
    fsx_mount_name = var.enable_fsx_lustre ? aws_fsx_lustre_file_system.gpu[0].mount_name : ""
  }))

  # ---------------------------------------------------------------------
  # 33 interfaces. When network_interfaces is set here you must NOT also set
  # subnet_id / security_group_ids at the instance level — the API rejects it.
  # ---------------------------------------------------------------------
  dynamic "network_interfaces" {
    for_each = local.efa_interfaces
    content {
      network_card_index    = network_interfaces.value.card
      device_index          = network_interfaces.value.device
      interface_type        = network_interfaces.value.type
      security_groups       = [aws_security_group.gpu.id]
      subnet_id             = aws_subnet.efa.id
      delete_on_termination = true
    }
  }

  # IMDSv2 only — IMDSv1 is an SSRF credential-theft path, and GPU nodes hold
  # the most valuable instance profile in the account.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "enabled"
  }

  block_device_mappings {
    device_name = "/dev/sda1"
    ebs {
      volume_size           = var.root_volume_size_gib
      volume_type           = "gp3"
      iops                  = 16000
      throughput            = 1000
      encrypted             = true
      kms_key_id            = var.kms_key_arn != "" ? var.kms_key_arn : null
      delete_on_termination = true
    }
  }

  # Local NVMe (8 x 3.84 TB = 30.4 TB) is instance-store: it is the fastest
  # place for sharded rollout buffers, but it is EPHEMERAL. Checkpoints must
  # land on FSx or S3, never only on instance store.
  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${var.name_prefix}-node"
    }
  }

  tag_specifications {
    resource_type = "volume"
    tags          = { Name = "${var.name_prefix}-root" }
  }

  monitoring { enabled = true }

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${var.name_prefix}-lt" }
}

resource "aws_instance" "gpu" {
  count = var.instance_count

  launch_template {
    id      = aws_launch_template.gpu.id
    version = aws_launch_template.gpu.latest_version
  }

  # Bind the node to the purchased reservation. Without this the instance
  # launches on-demand at a much higher effective rate (or fails outright).
  capacity_reservation_specification {
    capacity_reservation_preference = "open"

    capacity_reservation_target {
      capacity_reservation_id = aws_ec2_capacity_block_reservation.gpu.id
    }
  }

  # No placement_group here: Capacity Blocks do not support them and the
  # launch is rejected if one is set. The block is already inside an
  # UltraCluster, so nothing is lost.

  # Rollout buffers and NCCL graphs are memory-hungry; the node carries 2 TiB,
  # so do not let a stale AMI default cap it.
  instance_initiated_shutdown_behavior = "terminate"

  depends_on = [
    aws_ec2_capacity_block_reservation.gpu,
  ]

  tags = {
    Name = "${var.name_prefix}-node-${count.index}"
    Role = "gpu-worker"
  }
}

# =============================================================================
# AWS Compute Module
# =============================================================================

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "this" {
  count = var.instance_count

  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_ids[count.index % length(var.subnet_ids)]
  vpc_security_group_ids = [var.security_group_id]

  root_block_device {
    volume_size           = var.root_volume_size
    volume_type           = "gp3"
    encrypted             = var.enable_encryption
    delete_on_termination = true
  }

  monitoring = var.enable_monitoring

  tags = merge(var.common_tags, {
    Name = "${var.instance_name}-${count.index + 1}"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_eip" "this" {
  count = var.enable_elastic_ip ? var.instance_count : 0

  instance = aws_instance.this[count.index].id
  domain   = "vpc"

  tags = merge(var.common_tags, {
    Name = "${var.instance_name}-${count.index + 1}-eip"
  })
}

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

data "aws_ami" "this" {
  most_recent = true
  owners      = var.ami_owners

  filter {
    name   = "name"
    values = [var.ami_name_filter]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "this" {
  count = var.instance_count

  ami                    = var.ami_id != null ? var.ami_id : data.aws_ami.this.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_ids[count.index % length(var.subnet_ids)]
  vpc_security_group_ids = var.security_group_ids
  key_name               = var.key_name
  iam_instance_profile   = var.iam_instance_profile
  user_data              = var.user_data
  monitoring             = var.detailed_monitoring

  root_block_device {
    volume_size           = var.root_volume_size
    volume_type           = var.root_volume_type
    encrypted             = var.root_volume_encrypted
    delete_on_termination = true
  }

  dynamic "ebs_block_device" {
    for_each = var.additional_volumes
    content {
      device_name           = ebs_block_device.value.device_name
      volume_size           = ebs_block_device.value.volume_size
      volume_type           = ebs_block_device.value.volume_type
      encrypted             = ebs_block_device.value.encrypted
      delete_on_termination = true
    }
  }

  tags = merge(var.tags, {
    Name = "${var.name}-${count.index + 1}"
  })

  lifecycle {
    ignore_changes = [ami]
  }
}

resource "aws_eip" "this" {
  count    = var.assign_elastic_ip ? var.instance_count : 0
  domain   = "vpc"
  instance = aws_instance.this[count.index].id

  tags = merge(var.tags, {
    Name = "${var.name}-eip-${count.index + 1}"
  })
}

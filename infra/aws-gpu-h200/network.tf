# =============================================================================
# Network — dedicated VPC with an EFA-capable subnet
# =============================================================================
# EFA requires the instance and its peers to share a subnet with enough
# addresses for 32 interfaces per node. A /24 gives 251 usable addresses, which
# covers 7 nodes at 33 interfaces each; size up for larger clusters.

resource "aws_vpc" "gpu" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "${var.name_prefix}-vpc" }
}

resource "aws_internet_gateway" "gpu" {
  vpc_id = aws_vpc.gpu.id

  tags = { Name = "${var.name_prefix}-igw" }
}

resource "aws_subnet" "efa" {
  vpc_id            = aws_vpc.gpu.id
  cidr_block        = var.efa_subnet_cidr
  availability_zone = data.aws_availability_zones.available.names[0]

  # Public IPs on a multi-NIC GPU node cause hostname/source-IP mismatches and
  # are explicitly called out by AWS as an EFA anti-pattern. All egress goes
  # through the NAT gateway on the primary interface.
  map_public_ip_on_launch = false

  tags = { Name = "${var.name_prefix}-efa-subnet" }
}

data "aws_availability_zones" "available" {
  state = "available"

  # p5e/p5en are not in every AZ. Filter to zones that actually offer the
  # instance type so `terraform apply` fails at plan time, not at launch.
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.gpu.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gpu.id
  }

  tags = { Name = "${var.name_prefix}-public-rt" }
}

resource "aws_route_table_association" "efa" {
  subnet_id      = aws_subnet.efa.id
  route_table_id = aws_route_table.public.id
}

# ---------------------------------------------------------------------------
# Egress — container images, pip wheels, model weights
# ---------------------------------------------------------------------------

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = { Name = "${var.name_prefix}-nat-eip" }
}

resource "aws_nat_gateway" "gpu" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.efa.id

  depends_on = [aws_internet_gateway.gpu]

  tags = { Name = "${var.name_prefix}-nat" }
}

# ---------------------------------------------------------------------------
# Flow logs — required for the DCC evidence chain
# ---------------------------------------------------------------------------

resource "aws_flow_log" "gpu" {
  vpc_id               = aws_vpc.gpu.id
  traffic_type         = "ALL"
  log_destination_type = "cloud-watch-logs"
  log_destination      = aws_cloudwatch_log_group.flow_log.arn
  iam_role_arn         = aws_iam_role.flow_log.arn

  tags = { Name = "${var.name_prefix}-flow-log" }
}

resource "aws_cloudwatch_log_group" "flow_log" {
  name              = "/aws/vpc/${var.name_prefix}/flow-logs"
  retention_in_days = 90
  kms_key_id        = var.kms_key_arn != "" ? var.kms_key_arn : null

  tags = { Name = "${var.name_prefix}-flow-log-group" }
}

# ---------------------------------------------------------------------------
# Security groups
# ---------------------------------------------------------------------------

resource "aws_security_group" "gpu" {
  name_prefix = "${var.name_prefix}-gpu-"
  description = "GPU cluster nodes: intra-cluster RDMA/EFA, no public ingress"
  vpc_id      = aws_vpc.gpu.id

  # All intra-cluster traffic: NCCL, EFA bootstrap, Ray/Gloo rendezvous,
  # distributed checkpointing. Self-referencing keeps it cluster-scoped.
  ingress {
    description = "Intra-cluster all traffic (NCCL/EFA/Ray)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  dynamic "ingress" {
    for_each = var.allowed_ssh_cidrs
    content {
      description = "SSH from approved CIDR"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    description = "Egress for image pulls, package installs, and telemetry"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${var.name_prefix}-gpu-sg" }
}

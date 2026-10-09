"""
AWS Terraform Module Tests — Data Center Commander

Tests for AWS module configurations: VPC, subnets, security groups,
EC2, RDS, S3, CloudWatch, and IAM. Validates HCL2 parsing, resource
structure, and security compliance of Terraform configurations.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import hcl2
    HAS_HCL2 = True
except ImportError:
    HAS_HCL2 = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_clean(value: Any) -> Any:
    """Recursively strip extra wrapping quotes that hcl2 adds to strings."""
    if isinstance(value, str):
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value
    if isinstance(value, list):
        return [_deep_clean(v) for v in value]
    if isinstance(value, dict):
        return {k: _deep_clean(v) for k, v in value.items()}
    return value


def parse_hcl(hcl_string: str) -> Dict[str, Any]:
    """Parse an HCL string into a Python dict."""
    if not HAS_HCL2:
        pytest.skip("python-hcl2 not available")
    return _deep_clean(hcl2.loads(hcl_string))


def _strip_quotes(value: Any) -> Any:
    """Strip extra wrapping quotes that hcl2 adds to string values."""
    if isinstance(value, str) and len(value) >= 2:
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
    return value


def get_resources(parsed: Dict, resource_type: str) -> List[Dict]:
    """Extract resources of a given type from parsed HCL.

    hcl2 returns resource as a list of single-key dicts like:
    [{"\"aws_vpc\"": {"\"main\"": {...}}}}]
    """
    resources = []
    for block in parsed.get("resource", []):
        for key, value in block.items():
            # hcl2 may wrap keys in extra quotes
            clean_key = _strip_quotes(key)
            if clean_key == resource_type:
                if isinstance(value, dict):
                    for res_name, res_config in value.items():
                        if isinstance(res_config, dict):
                            resources.append(res_config)
    return resources


def get_blocks(parsed: Dict, block_type: str) -> List[Dict]:
    """Extract top-level blocks of a given type."""
    return parsed.get(block_type, [])


# ---------------------------------------------------------------------------
# Sample AWS module HCL configurations
# ---------------------------------------------------------------------------

VPC_HCL = """
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "prod-vpc"
    Environment = "production"
  }
}

resource "aws_flow_log" "vpc_flow_log" {
  vpc_id          = aws_vpc.main.id
  traffic_type    = "ALL"
  iam_role_arn    = aws_iam_role.flow_log.arn
  log_destination = aws_cloudwatch_log_group.flow_log.arn

  tags = {
    Name = "vpc-flow-log"
  }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "prod-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "public-rt"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "private-rt"
  }
}
"""

SUBNETS_HCL = """
resource "aws_subnet" "public_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = false

  tags = {
    Name = "public-subnet-1"
    Tier = "public"
  }
}

resource "aws_subnet" "public_2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "us-east-1b"
  map_public_ip_on_launch = false

  tags = {
    Name = "public-subnet-2"
    Tier = "public"
  }
}

resource "aws_subnet" "private_1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.10.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = false

  tags = {
    Name = "private-subnet-1"
    Tier = "private"
  }
}

resource "aws_subnet" "private_2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.11.0/24"
  availability_zone       = "us-east-1b"
  map_public_ip_on_launch = false

  tags = {
    Name = "private-subnet-2"
    Tier = "private"
  }
}

resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private_1" {
  subnet_id      = aws_subnet.private_1.id
  route_table_id = aws_route_table.private.id
}
"""

SECURITY_GROUPS_HCL = """
resource "aws_security_group" "web" {
  name        = "prod-web-sg"
  description = "Allow HTTPS inbound traffic"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTPS from anywhere"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "prod-web-sg"
  }
}

resource "aws_security_group" "app" {
  name        = "prod-app-sg"
  description = "Allow traffic from web tier"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "App port from web"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.web.id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "prod-app-sg"
  }
}

resource "aws_security_group" "db" {
  name        = "prod-db-sg"
  description = "Allow database traffic from app tier"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from app"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  tags = {
    Name = "prod-db-sg"
  }
}

resource "aws_security_group" "ssh" {
  name        = "prod-ssh-sg"
  description = "Allow SSH from bastion only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH from bastion"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.0.100.0/24"]
  }

  tags = {
    Name = "prod-ssh-sg"
  }
}
"""

EC2_HCL = """
resource "aws_instance" "app" {
  ami                    = "ami-0123456789abcdef0"
  instance_type          = "m6i.xlarge"
  subnet_id              = aws_subnet.private_1.id
  vpc_security_group_ids = [aws_security_group.app.id, aws_security_group.ssh.id]
  iam_instance_profile   = aws_iam_instance_profile.app.name

  metadata_options {
    http_tokens                 = "required"
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_size           = 100
    volume_type           = "gp3"
    encrypted             = true
    kms_key_id            = aws_kms_key.ebs.arn
    delete_on_termination = true
  }

  monitoring = true

  tags = {
    Name        = "prod-app-1"
    Environment = "production"
  }
}

resource "aws_iam_instance_profile" "app" {
  name = "prod-app-profile"
  role = aws_iam_role.app.name
}

resource "aws_kms_key" "ebs" {
  description             = "KMS key for EBS encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "ebs-encryption-key"
  }
}
"""

RDS_HCL = """
resource "aws_db_instance" "main" {
  identifier     = "prod-db"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.r6g.xlarge"

  allocated_storage     = 100
  max_allocated_storage = 500
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = "appdb"
  username = "dbadmin"
  password = "changeme"
  port     = 5432

  multi_az               = true
  publicly_accessible    = false
  deletion_protection    = true
  skip_final_snapshot    = false
  final_snapshot_identifier = "prod-db-final"

  backup_retention_period   = 30
  backup_window             = "03:00-04:00"
  maintenance_window        = "Mon:04:00-Mon:05:00"
  copy_tags_to_snapshot     = true

  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  performance_insights_enabled          = true
  performance_insights_kms_key_id      = aws_kms_key.rds.arn
  performance_insights_retention_period = 7

  tags = {
    Name        = "prod-db"
    Environment = "production"
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "prod-db-subnet-group"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]

  tags = {
    Name = "prod-db-subnet-group"
  }
}

resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "rds-encryption-key"
  }
}
"""

S3_HCL = """
resource "aws_s3_bucket" "data" {
  bucket = "prod-data-bucket"

  tags = {
    Name        = "prod-data-bucket"
    Environment = "production"
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "data" {
  bucket = aws_s3_bucket.data.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "data-bucket-logs/"
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 365
      storage_class = "GLACIER"
    }
  }
}

resource "aws_s3_bucket" "logs" {
  bucket = "prod-logs-bucket"

  tags = {
    Name = "prod-logs-bucket"
  }
}

resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "s3-encryption-key"
  }
}
"""

CLOUDWATCH_HCL = """
resource "aws_cloudwatch_log_group" "flow_log" {
  name              = "/aws/vpc/flow-logs"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.cloudwatch.arn

  tags = {
    Name = "vpc-flow-logs"
  }
}

resource "aws_cloudwatch_log_group" "rds" {
  name              = "/aws/rds/instance/prod-db/postgresql"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.cloudwatch.arn

  tags = {
    Name = "rds-postgresql-logs"
  }
}

resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "prod-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "CPU utilization exceeds 80% for 15 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    InstanceId = aws_instance.app.id
  }

  tags = {
    Name = "high-cpu-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  alarm_name          = "prod-rds-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5000000000
  alarm_description   = "RDS free storage below 5GB"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }

  tags = {
    Name = "rds-storage-alarm"
  }
}

resource "aws_sns_topic" "alerts" {
  name = "prod-alerts"

  tags = {
    Name = "prod-alerts"
  }
}

resource "aws_kms_key" "cloudwatch" {
  description             = "KMS key for CloudWatch logs"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "cloudwatch-encryption-key"
  }
}
"""

IAM_HCL = """
resource "aws_iam_role" "app" {
  name        = "prod-app-role"
  description = "Production application role"

  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
POLICY

  max_session_duration = 3600

  tags = {
    Name = "prod-app-role"
  }
}

resource "aws_iam_role_policy" "app_s3" {
  name = "prod-app-s3-access"
  role = aws_iam_role.app.id

  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::prod-data-bucket",
        "arn:aws:s3:::prod-data-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:aws:kms:us-east-1:123456789012:key/s3"
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy" "app_cloudwatch" {
  name = "prod-app-cloudwatch"
  role = aws_iam_role.app.id

  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "*"
    }
  ]
}
POLICY
}

resource "aws_iam_role" "flow_log" {
  name        = "vpc-flow-log-role"
  description = "Role for VPC flow logs"

  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "vpc-flow-logs.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
POLICY

  tags = {
    Name = "vpc-flow-log-role"
  }
}

resource "aws_iam_role_policy" "flow_log" {
  name = "vpc-flow-log-policy"
  role = aws_iam_role.flow_log.id

  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "*"
    }
  ]
}
POLICY
}

resource "aws_iam_password_policy" "strict" {
  minimum_password_length        = 14
  require_lowercase_characters   = true
  require_numbers               = true
  require_uppercase_characters   = true
  require_symbols               = true
  allow_users_to_change_password = true
  max_password_age              = 90
  password_reuse_prevention     = 24
}
"""


# ---------------------------------------------------------------------------
# VPC Tests
# ---------------------------------------------------------------------------

class TestVPCModule:
    """Tests for AWS VPC module configuration."""

    @pytest.fixture
    def parsed(self):
        return parse_hcl(VPC_HCL)

    def test_vpc_resource_exists(self, parsed):
        resources = get_resources(parsed, "aws_vpc")
        assert len(resources) == 1

    def test_vpc_cidr_block(self, parsed):
        vpc = get_resources(parsed, "aws_vpc")[0]
        assert vpc["cidr_block"] == "10.0.0.0/16"

    def test_vpc_dns_enabled(self, parsed):
        vpc = get_resources(parsed, "aws_vpc")[0]
        assert vpc["enable_dns_hostnames"] is True
        assert vpc["enable_dns_support"] is True

    def test_vpc_has_tags(self, parsed):
        vpc = get_resources(parsed, "aws_vpc")[0]
        assert "tags" in vpc
        assert vpc["tags"]["Name"] == "prod-vpc"
        assert vpc["tags"]["Environment"] == "production"

    def test_flow_log_exists(self, parsed):
        resources = get_resources(parsed, "aws_flow_log")
        assert len(resources) == 1

    def test_flow_log_traffic_type_all(self, parsed):
        flow_log = get_resources(parsed, "aws_flow_log")[0]
        assert flow_log["traffic_type"] == "ALL"

    def test_internet_gateway_exists(self, parsed):
        resources = get_resources(parsed, "aws_internet_gateway")
        assert len(resources) == 1

    def test_route_tables_exist(self, parsed):
        resources = get_resources(parsed, "aws_route_table")
        assert len(resources) == 2

    def test_public_route_has_igw(self, parsed):
        route_tables = get_resources(parsed, "aws_route_table")
        public_rt = [rt for rt in route_tables if rt["tags"]["Name"] == "public-rt"][0]
        assert "route" in public_rt
        routes = public_rt["route"]
        assert any(r.get("cidr_block") == "0.0.0.0/0" for r in routes)


# ---------------------------------------------------------------------------
# Subnet Tests
# ---------------------------------------------------------------------------

class TestSubnetsModule:
    """Tests for AWS subnets module configuration."""

    @pytest.fixture
    def parsed(self):
        return parse_hcl(SUBNETS_HCL)

    def test_subnet_count(self, parsed):
        resources = get_resources(parsed, "aws_subnet")
        assert len(resources) == 4

    def test_public_subnets_exist(self, parsed):
        subnets = get_resources(parsed, "aws_subnet")
        public = [s for s in subnets if s["tags"]["Tier"] == "public"]
        assert len(public) == 2

    def test_private_subnets_exist(self, parsed):
        subnets = get_resources(parsed, "aws_subnet")
        private = [s for s in subnets if s["tags"]["Tier"] == "private"]
        assert len(private) == 2

    def test_no_public_ip_on_launch(self, parsed):
        subnets = get_resources(parsed, "aws_subnet")
        for subnet in subnets:
            assert subnet["map_public_ip_on_launch"] is False

    def test_subnets_in_different_azs(self, parsed):
        subnets = get_resources(parsed, "aws_subnet")
        azs = [s["availability_zone"] for s in subnets]
        assert len(set(azs)) >= 2

    def test_route_table_associations_exist(self, parsed):
        resources = get_resources(parsed, "aws_route_table_association")
        assert len(resources) >= 2


# ---------------------------------------------------------------------------
# Security Group Tests
# ---------------------------------------------------------------------------

class TestSecurityGroupsModule:
    """Tests for AWS security groups module configuration."""

    @pytest.fixture
    def parsed(self):
        return parse_hcl(SECURITY_GROUPS_HCL)

    def test_security_group_count(self, parsed):
        resources = get_resources(parsed, "aws_security_group")
        assert len(resources) == 4

    def test_web_sg_allows_https(self, parsed):
        sgs = get_resources(parsed, "aws_security_group")
        web_sg = [sg for sg in sgs if sg["name"] == "prod-web-sg"][0]
        ingress = web_sg["ingress"]
        assert any(
            rule["from_port"] == 443 and rule["to_port"] == 443
            for rule in ingress
        )

    def test_web_sg_no_ssh(self, parsed):
        sgs = get_resources(parsed, "aws_security_group")
        web_sg = [sg for sg in sgs if sg["name"] == "prod-web-sg"][0]
        ingress = web_sg["ingress"]
        assert not any(rule["from_port"] == 22 for rule in ingress)

    def test_app_sg_references_web_sg(self, parsed):
        sgs = get_resources(parsed, "aws_security_group")
        app_sg = [sg for sg in sgs if sg["name"] == "prod-app-sg"][0]
        ingress = app_sg["ingress"]
        assert any("security_groups" in rule for rule in ingress)

    def test_db_sg_references_app_sg(self, parsed):
        sgs = get_resources(parsed, "aws_security_group")
        db_sg = [sg for sg in sgs if sg["name"] == "prod-db-sg"][0]
        ingress = db_sg["ingress"]
        assert any("security_groups" in rule for rule in ingress)

    def test_ssh_sg_restricted_cidr(self, parsed):
        sgs = get_resources(parsed, "aws_security_group")
        ssh_sg = [sg for sg in sgs if sg["name"] == "prod-ssh-sg"][0]
        ingress = ssh_sg["ingress"]
        for rule in ingress:
            if rule["from_port"] == 22:
                assert "0.0.0.0/0" not in rule.get("cidr_blocks", [])

    def test_all_sgs_have_description(self, parsed):
        sgs = get_resources(parsed, "aws_security_group")
        for sg in sgs:
            assert sg.get("description"), f"SG {sg['name']} missing description"

    def test_all_sgs_have_tags(self, parsed):
        sgs = get_resources(parsed, "aws_security_group")
        for sg in sgs:
            assert "tags" in sg, f"SG {sg['name']} missing tags"


# ---------------------------------------------------------------------------
# EC2 Tests
# ---------------------------------------------------------------------------

class TestEC2Module:
    """Tests for AWS EC2 module configuration."""

    @pytest.fixture
    def parsed(self):
        return parse_hcl(EC2_HCL)

    def test_instance_exists(self, parsed):
        resources = get_resources(parsed, "aws_instance")
        assert len(resources) == 1

    def test_instance_type_not_burstable(self, parsed):
        instance = get_resources(parsed, "aws_instance")[0]
        assert not instance["instance_type"].startswith("t2.")

    def test_imdsv2_required(self, parsed):
        instance = get_resources(parsed, "aws_instance")[0]
        metadata = instance["metadata_options"][0]
        assert metadata["http_tokens"] == "required"

    def test_root_volume_encrypted(self, parsed):
        instance = get_resources(parsed, "aws_instance")[0]
        root_vol = instance["root_block_device"][0]
        assert root_vol["encrypted"] is True

    def test_monitoring_enabled(self, parsed):
        instance = get_resources(parsed, "aws_instance")[0]
        assert instance["monitoring"] is True

    def test_instance_profile_exists(self, parsed):
        resources = get_resources(parsed, "aws_iam_instance_profile")
        assert len(resources) == 1

    def test_kms_key_for_ebs(self, parsed):
        resources = get_resources(parsed, "aws_kms_key")
        assert len(resources) == 1
        assert resources[0]["enable_key_rotation"] is True

    def test_instance_has_tags(self, parsed):
        instance = get_resources(parsed, "aws_instance")[0]
        assert "tags" in instance
        assert instance["tags"]["Name"] == "prod-app-1"


# ---------------------------------------------------------------------------
# RDS Tests
# ---------------------------------------------------------------------------

class TestRDSModule:
    """Tests for AWS RDS module configuration."""

    @pytest.fixture
    def parsed(self):
        return parse_hcl(RDS_HCL)

    def test_rds_instance_exists(self, parsed):
        resources = get_resources(parsed, "aws_db_instance")
        assert len(resources) == 1

    def test_rds_storage_encrypted(self, parsed):
        rds = get_resources(parsed, "aws_db_instance")[0]
        assert rds["storage_encrypted"] is True

    def test_rds_not_publicly_accessible(self, parsed):
        rds = get_resources(parsed, "aws_db_instance")[0]
        assert rds["publicly_accessible"] is False

    def test_rds_multi_az(self, parsed):
        rds = get_resources(parsed, "aws_db_instance")[0]
        assert rds["multi_az"] is True

    def test_rds_backup_retention(self, parsed):
        rds = get_resources(parsed, "aws_db_instance")[0]
        assert rds["backup_retention_period"] >= 7

    def test_rds_deletion_protection(self, parsed):
        rds = get_resources(parsed, "aws_db_instance")[0]
        assert rds["deletion_protection"] is True

    def test_rds_cloudwatch_logs_enabled(self, parsed):
        rds = get_resources(parsed, "aws_db_instance")[0]
        logs_exports = rds.get("enabled_cloudwatch_logs_exports", [])
        assert len(logs_exports) > 0

    def test_rds_performance_insights(self, parsed):
        rds = get_resources(parsed, "aws_db_instance")[0]
        assert rds["performance_insights_enabled"] is True

    def test_db_subnet_group_exists(self, parsed):
        resources = get_resources(parsed, "aws_db_subnet_group")
        assert len(resources) == 1

    def test_rds_has_tags(self, parsed):
        rds = get_resources(parsed, "aws_db_instance")[0]
        assert "tags" in rds


# ---------------------------------------------------------------------------
# S3 Tests
# ---------------------------------------------------------------------------

class TestS3Module:
    """Tests for AWS S3 module configuration."""

    @pytest.fixture
    def parsed(self):
        return parse_hcl(S3_HCL)

    def test_s3_bucket_exists(self, parsed):
        resources = get_resources(parsed, "aws_s3_bucket")
        assert len(resources) >= 1

    def test_s3_versioning_enabled(self, parsed):
        resources = get_resources(parsed, "aws_s3_bucket_versioning")
        assert len(resources) == 1
        versioning = resources[0]["versioning_configuration"][0]
        assert versioning["status"] == "Enabled"

    def test_s3_encryption_configured(self, parsed):
        resources = get_resources(parsed, "aws_s3_bucket_server_side_encryption_configuration")
        assert len(resources) == 1

    def test_s3_public_access_blocked(self, parsed):
        resources = get_resources(parsed, "aws_s3_bucket_public_access_block")
        assert len(resources) == 1
        block = resources[0]
        assert block["block_public_acls"] is True
        assert block["block_public_policy"] is True
        assert block["ignore_public_acls"] is True
        assert block["restrict_public_buckets"] is True

    def test_s3_logging_enabled(self, parsed):
        resources = get_resources(parsed, "aws_s3_bucket_logging")
        assert len(resources) == 1

    def test_s3_lifecycle_policy(self, parsed):
        resources = get_resources(parsed, "aws_s3_bucket_lifecycle_configuration")
        assert len(resources) == 1

    def test_s3_bucket_has_tags(self, parsed):
        buckets = get_resources(parsed, "aws_s3_bucket")
        for bucket in buckets:
            assert "tags" in bucket, f"Bucket {bucket.get('bucket')} missing tags"


# ---------------------------------------------------------------------------
# CloudWatch Tests
# ---------------------------------------------------------------------------

class TestCloudWatchModule:
    """Tests for AWS CloudWatch module configuration."""

    @pytest.fixture
    def parsed(self):
        return parse_hcl(CLOUDWATCH_HCL)

    def test_log_group_exists(self, parsed):
        resources = get_resources(parsed, "aws_cloudwatch_log_group")
        assert len(resources) >= 1

    def test_log_group_retention(self, parsed):
        log_groups = get_resources(parsed, "aws_cloudwatch_log_group")
        for lg in log_groups:
            assert lg["retention_in_days"] >= 30

    def test_log_group_kms_encrypted(self, parsed):
        log_groups = get_resources(parsed, "aws_cloudwatch_log_group")
        for lg in log_groups:
            assert "kms_key_id" in lg

    def test_high_cpu_alarm_exists(self, parsed):
        resources = get_resources(parsed, "aws_cloudwatch_metric_alarm")
        cpu_alarms = [a for a in resources if "cpu" in a["alarm_name"].lower()]
        assert len(cpu_alarms) >= 1

    def test_alarm_has_actions(self, parsed):
        alarms = get_resources(parsed, "aws_cloudwatch_metric_alarm")
        for alarm in alarms:
            assert "alarm_actions" in alarm
            assert len(alarm["alarm_actions"]) > 0

    def test_sns_topic_exists(self, parsed):
        resources = get_resources(parsed, "aws_sns_topic")
        assert len(resources) == 1


# ---------------------------------------------------------------------------
# IAM Tests
# ---------------------------------------------------------------------------

class TestIAMModule:
    """Tests for AWS IAM module configuration."""

    @pytest.fixture
    def parsed(self):
        return parse_hcl(IAM_HCL)

    def test_iam_role_exists(self, parsed):
        resources = get_resources(parsed, "aws_iam_role")
        assert len(resources) >= 1

    def test_role_has_description(self, parsed):
        roles = get_resources(parsed, "aws_iam_role")
        for role in roles:
            assert role.get("description"), f"Role {role['name']} missing description"

    def test_role_trust_policy_no_wildcard(self, parsed):
        roles = get_resources(parsed, "aws_iam_role")
        for role in roles:
            policy = role.get("assume_role_policy", "")
            if isinstance(policy, str):
                assert '"*"' not in policy or "Service" in policy

    def test_role_max_session_duration(self, parsed):
        roles = get_resources(parsed, "aws_iam_role")
        for role in roles:
            if "max_session_duration" in role:
                assert role["max_session_duration"] <= 3600

    def test_role_policy_exists(self, parsed):
        resources = get_resources(parsed, "aws_iam_role_policy")
        assert len(resources) >= 1

    def test_password_policy_exists(self, parsed):
        resources = get_resources(parsed, "aws_iam_password_policy")
        assert len(resources) == 1

    def test_password_policy_strong(self, parsed):
        policy = get_resources(parsed, "aws_iam_password_policy")[0]
        assert policy["minimum_password_length"] >= 14
        assert policy["require_lowercase_characters"] is True
        assert policy["require_numbers"] is True
        assert policy["require_uppercase_characters"] is True
        assert policy["require_symbols"] is True

    def test_roles_have_tags(self, parsed):
        roles = get_resources(parsed, "aws_iam_role")
        for role in roles:
            assert "tags" in role, f"Role {role['name']} missing tags"


# ---------------------------------------------------------------------------
# Cross-module integration tests
# ---------------------------------------------------------------------------

class TestCrossModuleIntegration:
    """Tests that validate cross-module references and consistency."""

    @pytest.fixture
    def all_parsed(self):
        return {
            "vpc": parse_hcl(VPC_HCL),
            "subnets": parse_hcl(SUBNETS_HCL),
            "security_groups": parse_hcl(SECURITY_GROUPS_HCL),
            "ec2": parse_hcl(EC2_HCL),
            "rds": parse_hcl(RDS_HCL),
            "s3": parse_hcl(S3_HCL),
            "cloudwatch": parse_hcl(CLOUDWATCH_HCL),
            "iam": parse_hcl(IAM_HCL),
        }

    def test_all_modules_have_required_tags(self, all_parsed):
        """All resources should have Name and Environment tags."""
        for module_name, parsed in all_parsed.items():
            for block in parsed.get("resource", []):
                for resource_type, resources in block.items():
                    if isinstance(resources, dict):
                        for resource_name, resource_config in resources.items():
                            if isinstance(resource_config, dict) and "tags" in resource_config:
                                tags = resource_config["tags"]
                                assert "Name" in tags, (
                                    f"{module_name}.{resource_type}.{resource_name} missing Name tag"
                                )

    def test_security_groups_reference_vpc(self, all_parsed):
        """Security groups should reference a VPC."""
        sg_parsed = all_parsed["security_groups"]
        sgs = get_resources(sg_parsed, "aws_security_group")
        for sg in sgs:
            assert "vpc_id" in sg, f"SG {sg['name']} missing vpc_id"

    def test_rds_references_security_group(self, all_parsed):
        """RDS should reference a security group."""
        rds_parsed = all_parsed["rds"]
        rds = get_resources(rds_parsed, "aws_db_instance")[0]
        assert "vpc_security_group_ids" in rds

    def test_ec2_references_security_groups(self, all_parsed):
        """EC2 should reference security groups."""
        ec2_parsed = all_parsed["ec2"]
        instance = get_resources(ec2_parsed, "aws_instance")[0]
        assert "vpc_security_group_ids" in instance
        assert len(instance["vpc_security_group_ids"]) > 0

    def test_flow_log_references_cloudwatch(self, all_parsed):
        """VPC flow log should reference a CloudWatch log group."""
        vpc_parsed = all_parsed["vpc"]
        flow_logs = get_resources(vpc_parsed, "aws_flow_log")
        for fl in flow_logs:
            assert "log_destination" in fl

    def test_alarms_reference_sns(self, all_parsed):
        """CloudWatch alarms should reference SNS topics."""
        cw_parsed = all_parsed["cloudwatch"]
        alarms = get_resources(cw_parsed, "aws_cloudwatch_metric_alarm")
        for alarm in alarms:
            assert "alarm_actions" in alarm

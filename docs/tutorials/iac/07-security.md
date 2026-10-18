# Tutorial 07: Security Infrastructure as Code

## Overview

Security must be embedded into every layer of your infrastructure. This tutorial covers how to implement security controls, manage secrets, enforce encryption, and maintain zero-trust architecture using Infrastructure as Code.

## Learning Objectives

- Implement security controls in IaC
- Manage secrets securely
- Enforce encryption at rest and in transit
- Implement network security
- Automate security auditing

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Layer 7: Application Security                       │   │
│  │  - WAF, API Gateway, Input Validation               │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Layer 6: Container/Pod Security                     │   │
│  │  - Network Policies, Pod Security, RBAC              │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Layer 5: Network Security                           │   │
│  │  - Security Groups, NACLs, Firewalls                │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Layer 4: Host Security                              │   │
│  │  - Hardened AMIs, Patch Management, CIS Benchmarks   │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Layer 3: Identity & Access                          │   │
│  │  - IAM, RBAC, Service Accounts, OIDC                 │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Layer 2: Secrets Management                         │   │
│  │  - Vault, KMS, Secrets Manager                       │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Layer 1: Encryption                                  │   │
│  │  - At Rest, In Transit, Key Management               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Secrets Management

### HashiCorp Vault

```hcl
# vault.tf
module "vault" {
  source          = "hashicorp/vault/aws"
  version         = "~> 0.17.0"
  vault_version   = "1.15.0"

  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets

  cluster_name    = "${var.environment}-vault"
  cluster_size    = 3

  enable_auto_unseal = true
  unseal_kms_key_id  = aws_kms_key.vault.arn

  tags = var.common_tags
}

# Enable KV secrets engine
resource "vault_mount" "secret" {
  path        = "secret"
  type        = "kv-v2"
  description = "KV Version 2 secrets engine"
}

# Store database credentials
resource "vault_kv_secret_v2" "database" {
  mount = vault_mount.secret.path
  name  = "database/credentials"

  data_json = jsonencode({
    username = var.db_username
    password = var.db_password
    host     = var.db_host
    port     = 5432
  })
}

# Enable database secrets engine
resource "vault_database_secrets_engine" "postgres" {
  name = "postgres"

  connection {
    plugin_name = "postgresql-database-plugin"
    allowed_roles = ["app", "admin"]
    connection_url = "postgresql://{{username}}:{{password}}@${var.db_host}:5432/postgres"
  }
}

# Dynamic database credentials
resource "vault_database_secret_backend_role" "app" {
  backend             = vault_database_secrets_engine.postgres.name
  name                = "app"
  db_name             = vault_database_secrets_engine.postgres.name
  creation_statements = [
    "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
    "GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";",
  ]
  default_ttl = 3600   # 1 hour
  max_ttl     = 86400  # 24 hours
}
```

### AWS Secrets Manager

```hcl
# secrets.tf
resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${var.environment}/database/password"
  description             = "Database password for ${var.environment}"
  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 7

  tags = var.common_tags
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id = aws_secretsmanager_secret.db_password.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db_password.result
    host     = aws_db_instance.main.address
    port     = 5432
    dbname   = "app"
  })
}

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Automatic rotation
resource "aws_secretsmanager_secret_rotation" "db_password" {
  secret_id           = aws_secretsmanager_secret.db_password.id
  rotation_lambda_arn = aws_lambda_function.rotation.arn

  rotation_rules {
    automatically_after_days = 30
  }
}
```

## Encryption

### KMS Key Management

```hcl
# kms.tf
resource "aws_kms_key" "main" {
  description             = "KMS key for ${var.environment} encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region            = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${var.region}.amazonaws.com"
        }
        Action = [
          "kms:Encrypt*",
          "kms:Decrypt*",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:Describe*"
        ]
        Resource = "*"
      }
    ]
  })

  tags = var.common_tags
}

resource "aws_kms_alias" "main" {
  name          = "alias/${var.environment}-main"
  target_key_id = aws_kms_key.main.key_id
}
```

### Encryption at Rest

```hcl
# EBS encryption
resource "aws_ebs_volume" "encrypted" {
  availability_zone = var.az
  size              = var.size_gb
  encrypted         = true
  kms_key_id        = aws_kms_key.main.arn
  type              = "gp3"

  tags = {
    Name = "${var.environment}-data-volume"
  }
}

# S3 bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.main.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# RDS encryption
resource "aws_db_instance" "main" {
  identifier     = "${var.environment}-db"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.t3.medium"

  storage_encrypted = true
  kms_key_id        = aws_kms_key.main.arn

  # ... other configuration
}
```

### Encryption in Transit

```hcl
# ACM Certificate
resource "aws_acm_certificate" "main" {
  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = var.common_tags
}

# TLS-only security group rules
resource "aws_security_group_rule" "https" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.web.id
  description       = "HTTPS inbound"
}

# Deny HTTP
resource "aws_security_group_rule" "deny_http" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.web.id
  description       = "HTTP - redirect to HTTPS"
}
```

## Network Security

### Security Groups

```hcl
# security_groups.tf
resource "aws_security_group" "web" {
  name_prefix = "${var.environment}-web-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for web servers"

  tags = merge(var.common_tags, {
    Name = "${var.environment}-web"
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "web_https_in" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.web.id
  description       = "HTTPS from anywhere"
}

resource "aws_security_group_rule" "web_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.web.id
  description       = "Allow all outbound"
}

resource "aws_security_group" "database" {
  name_prefix = "${var.environment}-db-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for databases"

  tags = merge(var.common_tags, {
    Name = "${var.environment}-db"
  })
}

resource "aws_security_group_rule" "db_postgres_in" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.web.id
  security_group_id        = aws_security_group.database.id
  description              = "PostgreSQL from web servers only"
}
```

### Network ACLs

```hcl
resource "aws_network_acl" "private" {
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Allow inbound from VPC
  ingress {
    protocol   = -1
    rule_no    = 100
    action     = "allow"
    cidr_block = module.vpc.vpc_cidr_block
    from_port  = 0
    to_port    = 0
  }

  # Allow outbound to VPC
  egress {
    protocol   = -1
    rule_no    = 100
    action     = "allow"
    cidr_block = module.vpc.vpc_cidr_block
    from_port  = 0
    to_port    = 0
  }

  # Allow inbound HTTPS from anywhere
  ingress {
    protocol   = "tcp"
    rule_no    = 200
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 443
    to_port    = 443
  }

  # Allow ephemeral ports
  ingress {
    protocol   = "tcp"
    rule_no    = 300
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }

  tags = merge(var.common_tags, {
    Name = "${var.environment}-private-nacl"
  })
}
```

### Web Application Firewall (WAF)

```hcl
# waf.tf
resource "aws_wafv2_web_acl" "main" {
  name        = "${var.environment}-waf"
  description = "WAF rules for ${var.environment}"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # AWS Managed Rules - Common Rule Set
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesCommonRuleSet"
      sampled_requests_enabled   = true
    }
  }

  # Rate limiting
  rule {
    name     = "RateLimit"
    priority = 2

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimit"
      sampled_requests_enabled   = true
    }
  }

  # Geo-blocking
  rule {
    name     = "GeoBlock"
    priority = 3

    action {
      block {}
    }

    statement {
      geo_match_statement {
        country_codes = var.blocked_countries
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "GeoBlock"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.environment}-waf"
    sampled_requests_enabled   = true
  }

  tags = var.common_tags
}
```

## Identity and Access Management

```hcl
# iam.tf
resource "aws_iam_role" "app" {
  name = "${var.environment}-app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy" "app" {
  name = "${var.environment}-app-policy"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Access"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.app.arn}/*"
        ]
      },
      {
        Sid    = "SecretsAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.app.arn
        ]
      },
      {
        Sid    = "KMSDecrypt"
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = [
          aws_kms_key.main.arn
        ]
      }
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:*:*:*"
        ]
      }
    ]
  })
}

# Permission boundaries
resource "aws_iam_policy" "permission_boundary" {
  name = "${var.environment}-permission-boundary"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowedServices"
        Effect = "Allow"
        Action = [
          "ec2:*",
          "s3:*",
          "rds:*",
          "secretsmanager:*",
          "kms:*",
          "logs:*",
          "cloudwatch:*"
        ]
        Resource = "*"
      },
      {
        Sid    = "DenyDangerousActions"
        Effect = "Deny"
        Action = [
          "iam:*",
          "organizations:*",
          "account:*"
        ]
        Resource = "*"
      }
    ]
  })
}
```

## Security Auditing

```hcl
# GuardDuty
resource "aws_guardduty_detector" "main" {
  enable = true

  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = true
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        enable = true
      }
    }
  }
}

# Security Hub
resource "aws_securityhub_account" "main" {
  enable_default_standards = false
}

resource "aws_securityhub_standards_subscription" "cis" {
  standards_arn = "arn:aws:securityhub:::ruleset/cis-aws-foundations-benchmark/v/1.2.0"
  depends_on    = [aws_securityhub_account.main]
}

resource "aws_securityhub_standards_subscription" "pci" {
  standards_arn = "arn:aws:securityhub:::ruleset/pci-dss/v/3.2.1"
  depends_on    = [aws_securityhub_account.main]
}

# Config Rules
resource "aws_config_config_rule" "encrypted_volumes" {
  name = "encrypted-volumes"

  source {
    owner             = "AWS"
    source_identifier = "EC2_EBS_ENCRYPTION_BY_DEFAULT"
  }
}

resource "aws_config_config_rule" "s3_bucket_encryption" {
  name = "s3-bucket-server-side-encryption-enabled"

  source {
    owner             = "AWS"
    source_identifier = "S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED"
  }
}
```

## Best Practices

1. **Principle of least privilege** — Grant minimum necessary permissions
2. **Rotate secrets automatically** — Use automatic rotation where possible
3. **Encrypt everything** — At rest and in transit, always
4. **Use private subnets** — Keep workloads off the public internet
5. **Enable logging everywhere** — CloudTrail, VPC Flow Logs, application logs
6. **Implement defense in depth** — Multiple security layers
7. **Scan for vulnerabilities** — Regular image and infrastructure scans
8. **Automate security testing** — Integrate security checks into CI/CD

## Next Steps

- [Tutorial 03: Compliance as Code](./03-compliance.md)
- [Tutorial 04: Policy as Code](./04-policy.md)
- [Tutorial 10: Monitoring](./10-monitoring.md)

## References

- [AWS Security Best Practices](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html)
- [HashiCorp Vault](https://www.vaultproject.io/)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks)
- [OWASP](https://owasp.org/)

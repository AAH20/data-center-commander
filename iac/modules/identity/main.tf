# =============================================================================
# Cross-Cloud Identity & IAM Module
# =============================================================================
# Manages identity and access control across cloud providers.
# Supports AWS IAM, GCP IAM, Azure RBAC, and IBM Cloud IAM.
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
    ibm = {
      source  = "IBM-Cloud/ibm"
      version = "~> 1.60"
    }
  }
}

###############################################################################
# AWS IAM
###############################################################################

resource "aws_iam_role" "workload" {
  count = var.enable_aws ? 1 : 0
  name  = "${var.project_name}-workload-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy" "workload" {
  count = var.enable_aws ? 1 : 0
  name  = "${var.project_name}-workload-policy"
  role  = aws_iam_role.workload[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "workload" {
  count = var.enable_aws ? 1 : 0
  name  = "${var.project_name}-workload-profile"
  role  = aws_iam_role.workload[0].name
}

###############################################################################
# GCP IAM
###############################################################################

resource "google_service_account" "workload" {
  count        = var.enable_gcp ? 1 : 0
  account_id   = "${var.project_name}-workload"
  display_name = "${var.project_name} workload service account"
  project      = var.gcp_project_id
}

resource "google_project_iam_member" "workload" {
  count   = var.enable_gcp ? length(var.gcp_workload_roles) : 0
  project = var.gcp_project_id
  role    = var.gcp_workload_roles[count.index]
  member  = "serviceAccount:${google_service_account.workload[0].email}"
}

###############################################################################
# Azure RBAC
###############################################################################

resource "azurerm_role_definition" "workload" {
  count       = var.enable_azure ? 1 : 0
  name        = "${var.project_name}-workload-role"
  scope       = var.azure_subscription_id
  description = "Custom role for ${var.project_name} workloads"

  permissions {
    actions = [
      "Microsoft.Compute/virtualMachines/read",
      "Microsoft.Storage/storageAccounts/blobServices/containers/read",
      "Microsoft.Network/networkInterfaces/read",
      "Microsoft.Insights/metrics/read"
    ]
    not_actions = []
  }

  assignable_scopes = [var.azure_subscription_id]
}

###############################################################################
# IBM Cloud IAM
###############################################################################

resource "ibm_iam_service_id" "workload" {
  count       = var.enable_ibm ? 1 : 0
  name        = "${var.project_name}-workload-sid"
  description = "Service ID for ${var.project_name} workloads"
}

resource "ibm_iam_service_policy" "workload" {
  count          = var.enable_ibm ? 1 : 0
  iam_service_id = ibm_iam_service_id.workload[0].iam_id
  roles          = ["Viewer", "Operator"]

  resources {
    service = "is"
  }
}

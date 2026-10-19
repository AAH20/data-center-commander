terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  # Capacity Block reservations cannot be deleted — destroying the stack only
  # removes the reservation from state while the capacity (and its cost) runs
  # to the end of the booked window. Use a locking remote backend so two
  # operators can never race a purchase.
  backend "s3" {
    # bucket         = "dcc-tfstate-<account-id>"
    # key            = "aws-gpu-h200/terraform.tfstate"
    # region         = "us-east-1"
    # dynamodb_table = "dcc-tfstate-lock"
    # encrypt        = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "data-center-commander"
      Component   = "gpu-agentic-compute"
      Environment = var.environment
      ManagedBy   = "terraform"
      # Cost-allocation tags — GPU spend is the single largest line item, so it
      # must be attributable per cluster and per workload team.
      CostCenter = var.cost_center
      Workload   = var.workload_class
    }
  }
}

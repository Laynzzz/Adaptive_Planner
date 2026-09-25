terraform {

  required_version = ">= 1.16.2, < 2.0.0"
  required_providers {

    aws    = { source = "hashicorp/aws", version = "~> 6.0" }
    random = { source = "hashicorp/random", version = "~> 3.7" }

  }

  # Bootstrap the encrypted, versioned state bucket separately; see backend.hcl.example.
  backend "s3" {

  }


}

provider "aws" {

  region = var.region
  default_tags {

    tags = local.tags
  }


}

locals {

  name = "${var.project}-${var.environment}"
  tags = { Project = var.project, Environment = var.environment, Owner = var.owner_tag, CostCenter = var.cost_center, ManagedBy = "Terraform", Retention = "demo-until-reviewed" }

}


variable "region" {

  type    = string
  default = "us-east-1"
  validation {

    condition     = var.region == "us-east-1"
    error_message = "This reviewed estimate and reference profile use us-east-1."
  }


}

variable "project" {

  type    = string
  default = "adaptive-planner"
}

variable "environment" {

  type    = string
  default = "demo"
}

variable "owner_tag" {

  type = string
}

variable "cost_center" {

  type = string
}

variable "application_origin" {

  type = string
  validation {

    condition     = can(regex("^https://[^/]+$", var.application_origin))
    error_message = "Use a single HTTPS origin without a path or trailing slash."
  }


}

variable "certificate_arn" {

  type = string
}

variable "cognito_domain_prefix" {

  type = string
}

variable "image" {

  type        = string
  description = "Reviewed application ECR image pinned by digest. Never latest."
  validation {

    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.image))
    error_message = "Deploy an immutable image digest."
  }


}

variable "collector_image" {

  type    = string
  default = "otel/opentelemetry-collector-contrib:0.148.0@sha256:8164eab2e6bca9c9b0837a8d2f118a6618489008a839db7f9d6510e66be3923c"
}

variable "budget_usd" {

  type = number
  validation {

    condition     = var.budget_usd > 0
    error_message = "An explicitly approved monthly budget is required; an alarm is not a spending cap."
  }


}

variable "budget_email" {

  type = string
}

variable "github_repository" {

  type        = string
  description = "owner/repository, restricted to GitHub environment release."
}

variable "github_oidc_provider_arn" {

  type        = string
  default     = ""
  description = "Existing account-wide GitHub OIDC provider, or empty to create it."
}

variable "desired_count" {

  type        = number
  default     = 0
  description = "Keep zero through bootstrap. Set one only after migration and approved release."
  validation {

    condition     = contains([0, 1], var.desired_count)
    error_message = "Reference demo allows zero or one task of each kind."
  }


}

variable "deletion_protection" {

  type    = bool
  default = true
}


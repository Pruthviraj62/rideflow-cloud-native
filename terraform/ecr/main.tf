terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0, < 7.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region for RideFlow"
  type        = string
  default     = "ap-south-1"
}

locals {
  services = toset([
    "rideflow-api-gateway",
    "rideflow-rider-service",
    "rideflow-driver-service",
    "rideflow-trip-service",
    "rideflow-pricing-service"
  ])
}

resource "aws_ecr_repository" "services" {
  for_each = local.services

  name                 = each.value
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Project     = "RideFlow"
    Environment = "development"
    ManagedBy   = "Terraform"
  }
}

resource "aws_ecr_lifecycle_policy" "services" {
  for_each   = aws_ecr_repository.services
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Retain the ten most recent images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}

output "repository_urls" {
  description = "ECR repository URLs for RideFlow services"

  value = {
    for name, repository in aws_ecr_repository.services :
    name => repository.repository_url
  }
}

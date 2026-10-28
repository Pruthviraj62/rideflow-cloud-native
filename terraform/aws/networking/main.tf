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

variable "project_name" {
  description = "Project identifier"
  type        = string
  default     = "rideflow"
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated RideFlow VPC"
  type        = string
  default     = "10.20.0.0/16"
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 3)

  public_subnets = {
    "${local.azs[0]}" = "10.20.0.0/20"
    "${local.azs[1]}" = "10.20.16.0/20"
    "${local.azs[2]}" = "10.20.32.0/20"
  }

  private_subnets = {
    "${local.azs[0]}" = "10.20.48.0/20"
    "${local.azs[1]}" = "10.20.64.0/20"
    "${local.azs[2]}" = "10.20.80.0/20"
  }

  common_tags = {
    Project     = "RideFlow"
    Environment = "development"
    ManagedBy   = "Terraform"
  }
}

resource "aws_vpc" "rideflow" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-vpc"
  })
}

resource "aws_internet_gateway" "rideflow" {
  vpc_id = aws_vpc.rideflow.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-igw"
  })
}

resource "aws_subnet" "public" {
  for_each = local.public_subnets

  vpc_id                  = aws_vpc.rideflow.id
  availability_zone       = each.key
  cidr_block              = each.value
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name                                 = "${var.project_name}-public-${each.key}"
    "kubernetes.io/role/elb"             = "1"
    "kubernetes.io/cluster/rideflow-eks" = "shared"
  })
}

resource "aws_subnet" "private" {
  for_each = local.private_subnets

  vpc_id            = aws_vpc.rideflow.id
  availability_zone = each.key
  cidr_block        = each.value

  tags = merge(local.common_tags, {
    Name                                 = "${var.project_name}-private-${each.key}"
    "kubernetes.io/role/internal-elb"    = "1"
    "kubernetes.io/cluster/rideflow-eks" = "shared"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.rideflow.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.rideflow.id
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  for_each = aws_subnet.public

  domain = "vpc"

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-nat-eip-${each.key}"
  })

  depends_on = [aws_internet_gateway.rideflow]
}

resource "aws_nat_gateway" "rideflow" {
  for_each = aws_subnet.public

  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = each.value.id

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-nat-${each.key}"
  })

  depends_on = [aws_internet_gateway.rideflow]
}

resource "aws_route_table" "private" {
  for_each = local.private_subnets

  vpc_id = aws_vpc.rideflow.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.rideflow[each.key].id
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-private-rt-${each.key}"
  })
}

resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private

  subnet_id      = each.value.id
  route_table_id = aws_route_table.private[each.key].id
}

output "vpc_id" {
  description = "RideFlow VPC ID"
  value       = aws_vpc.rideflow.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs by availability zone"
  value       = { for az, subnet in aws_subnet.public : az => subnet.id }
}

output "private_subnet_ids" {
  description = "Private subnet IDs by availability zone"
  value       = { for az, subnet in aws_subnet.private : az => subnet.id }
}

output "availability_zones" {
  description = "Availability zones used by RideFlow"
  value       = local.azs
}

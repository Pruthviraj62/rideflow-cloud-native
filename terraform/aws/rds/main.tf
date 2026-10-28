terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0, < 7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0, < 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "terraform_remote_state" "networking" {
  backend = "local"
  config = {
    path = "../networking/terraform.tfstate"
  }
}

data "aws_eks_cluster" "rideflow" {
  name = "rideflow-eks"
}

locals {
  common_tags = {
    Project     = "RideFlow"
    Environment = "development"
    ManagedBy   = "Terraform"
  }

  private_subnet_ids = values(
    data.terraform_remote_state.networking.outputs.private_subnet_ids
  )
}

resource "aws_db_subnet_group" "rideflow" {
  name        = "rideflow-postgres-subnets"
  description = "Private subnets for RideFlow PostgreSQL"
  subnet_ids  = local.private_subnet_ids

  tags = merge(local.common_tags, {
    Name = "rideflow-postgres-subnets"
  })
}

resource "aws_security_group" "postgres" {
  name        = "rideflow-postgres-sg"
  description = "Allow PostgreSQL from the RideFlow EKS cluster security group"
  vpc_id      = data.terraform_remote_state.networking.outputs.vpc_id

  ingress {
    description     = "PostgreSQL from EKS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [data.aws_eks_cluster.rideflow.vpc_config[0].cluster_security_group_id]
  }

  egress {
    description = "Allow outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "rideflow-postgres-sg"
  })
}

resource "random_password" "postgres" {
  length  = 24
  special = false
}

resource "aws_db_instance" "rideflow" {
  identifier     = "rideflow-postgres"
  engine         = "postgres"
  instance_class = var.instance_class

  db_name  = "rideflow"
  username = "rideflow_admin"
  password = random_password.postgres.result

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_subnet_group_name   = aws_db_subnet_group.rideflow.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  publicly_accessible    = false

  multi_az                   = false
  backup_retention_period    = 1
  auto_minor_version_upgrade = true
  deletion_protection        = false
  apply_immediately          = false

  skip_final_snapshot = true

  tags = merge(local.common_tags, {
    Name = "rideflow-postgres"
  })
}

output "db_endpoint" {
  description = "Private PostgreSQL endpoint"
  value       = aws_db_instance.rideflow.address
}

output "db_port" {
  description = "PostgreSQL port"
  value       = aws_db_instance.rideflow.port
}

output "db_name" {
  value = aws_db_instance.rideflow.db_name
}

output "db_username" {
  value = aws_db_instance.rideflow.username
}

output "db_password" {
  description = "Generated PostgreSQL password; keep secret"
  value       = random_password.postgres.result
  sensitive   = true
}

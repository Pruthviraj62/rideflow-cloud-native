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

data "terraform_remote_state" "networking" {
  backend = "local"

  config = {
    path = "../networking/terraform.tfstate"
  }
}

locals {
  cluster_name = "rideflow-eks"

  common_tags = {
    Project     = "RideFlow"
    Environment = "development"
    ManagedBy   = "Terraform"
  }
}

# EKS control-plane IAM role
resource "aws_iam_role" "cluster" {
  name = "${local.cluster_name}-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

# Worker-node IAM role
resource "aws_iam_role" "nodes" {
  name = "${local.cluster_name}-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "worker_policy" {
  role       = aws_iam_role.nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "cni_policy" {
  role       = aws_iam_role.nodes.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

# EKS control plane across all three AZs.
# Nodes will be placed only in private subnets.
resource "aws_eks_cluster" "main" {
  name     = local.cluster_name
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true
  }

  vpc_config {
    subnet_ids = concat(
      values(data.terraform_remote_state.networking.outputs.private_subnet_ids),
      values(data.terraform_remote_state.networking.outputs.public_subnet_ids)
    )

    endpoint_private_access = true
    endpoint_public_access  = false
    public_access_cidrs     = [var.admin_cidr]
  }

  enabled_cluster_log_types = [
    "api",
    "authenticator"
  ]

  tags = local.common_tags

  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy
  ]
}

# Small managed node group for the project demonstration.
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${local.cluster_name}-workers"
  node_role_arn   = aws_iam_role.nodes.arn

  subnet_ids = values(
    data.terraform_remote_state.networking.outputs.private_subnet_ids
  )

  instance_types = var.node_instance_types
  capacity_type  = "ON_DEMAND"
  disk_size      = 20

  scaling_config {
    min_size     = 2
    desired_size = 2
    max_size     = 3
  }

  update_config {
    max_unavailable = 1
  }

  tags = local.common_tags

  depends_on = [
    aws_iam_role_policy_attachment.worker_policy,
    aws_iam_role_policy_attachment.ecr_read,
    aws_iam_role_policy_attachment.cni_policy
  ]
}

# Resolve supported add-on versions from AWS for this Kubernetes version.



resource "aws_eks_addon" "vpc_cni" {
  cluster_name                = aws_eks_cluster.main.name
  addon_name                  = "vpc-cni"
  addon_version               = "v1.23.2-eksbuild.3"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  tags = local.common_tags

  depends_on = [aws_eks_node_group.main]
}

resource "aws_eks_addon" "coredns" {
  cluster_name                = aws_eks_cluster.main.name
  addon_name                  = "coredns"
  addon_version               = "v1.14.7-eksbuild.11"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  tags = local.common_tags

  depends_on = [aws_eks_node_group.main]
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name                = aws_eks_cluster.main.name
  addon_name                  = "kube-proxy"
  addon_version               = "v1.36.0-eksbuild.48"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  tags = local.common_tags

  depends_on = [aws_eks_node_group.main]
}

output "cluster_name" {
  value       = aws_eks_cluster.main.name
  description = "RideFlow EKS cluster name"
}

output "cluster_endpoint" {
  value       = aws_eks_cluster.main.endpoint
  description = "Kubernetes API endpoint"
}

output "cluster_version" {
  value       = aws_eks_cluster.main.version
  description = "Kubernetes version"
}

output "node_group_name" {
  value       = aws_eks_node_group.main.node_group_name
  description = "Managed worker node group"
}

output "vpc_id" {
  value       = data.terraform_remote_state.networking.outputs.vpc_id
  description = "VPC hosting RideFlow"
}

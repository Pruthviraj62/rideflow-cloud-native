variable "aws_region" {
  description = "AWS region for RideFlow"
  type        = string
  default     = "ap-south-1"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version verified in ap-south-1"
  type        = string
  default     = "1.36"
}

variable "admin_cidr" {
  description = "Public IPv4 CIDR permitted to reach the Kubernetes API"
  type        = string

  validation {
    condition     = can(cidrhost(var.admin_cidr, 0)) && endswith(var.admin_cidr, "/32")
    error_message = "admin_cidr must be a single IPv4 address with a /32 mask."
  }
}

variable "node_instance_types" {
  description = "EC2 instance types for the EKS managed node group"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "aws_region" {
  description = "AWS region for RideFlow"
  type        = string
  default     = "ap-south-1"
}

variable "instance_class" {
  description = "RDS instance class for the development environment"
  type        = string
  default     = "db.t3.micro"
}

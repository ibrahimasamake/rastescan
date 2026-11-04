variable "region" {
  description = "AWS region for everything. Mumbai is closest to Bengaluru."
  type        = string
  default     = "ap-south-1"
}

variable "bedrock_model_id" {
  description = "Nova model or inference profile id the app calls."
  type        = string
  default     = "apac.amazon.nova-pro-v1:0"
}

variable "instance_type" {
  description = "ARM instance size. t4g.small (2 GB) is enough for the demo."
  type        = string
  default     = "t4g.small"
}

variable "ssh_allowed_cidr" {
  description = "Your public IP in CIDR form, e.g. 203.0.113.7/32. Only this address can SSH in."
  type        = string
  validation {
    condition     = can(cidrhost(var.ssh_allowed_cidr, 0)) && var.ssh_allowed_cidr != "0.0.0.0/0"
    error_message = "Use your own IP with /32, not 0.0.0.0/0."
  }
}

variable "ssh_public_key_path" {
  description = "Public key Ansible will use to log in."
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "budget_email" {
  description = "Email that receives AWS budget alerts."
  type        = string
}

variable "budget_limit_usd" {
  description = "Monthly budget. Alerts fire at 20%, 50% and 80% of it."
  type        = number
  default     = 50
}

variable "create_budget" {
  description = "Create the AWS Budgets alert. Set false if your organization blocks the Budgets API."
  type        = bool
  default     = true
}

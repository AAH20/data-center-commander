variable "name" {
  description = "Name of the security group"
  type        = string
}

variable "description" {
  description = "Description of the security group"
  type        = string
  default     = ""
}

variable "rules" {
  description = "Map of security group rules (key = name)"
  type = map(object({
    cidr_list = list(string)
    protocol  = string
    icmp_code = number
    icmp_type = number
    ports     = list(string)
    type      = string
  }))
  default = {}
}

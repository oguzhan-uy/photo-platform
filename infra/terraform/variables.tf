variable "tenancy_ocid" {
  description = "OCID of your OCI tenancy. Found in Profile → Tenancy."
  type        = string
}

variable "user_ocid" {
  description = "OCID of the OCI user running Terraform."
  type        = string
}

variable "fingerprint" {
  description = "MD5 fingerprint of the API signing key (from Identity → API Keys)."
  type        = string
}

variable "private_key_path" {
  description = "Local path to the PEM private key that matches the fingerprint."
  type        = string
  default     = "~/.oci/oci_api_key.pem"
}

variable "region" {
  description = "OCI region. eu-frankfurt-1 gives EU residency for GDPR/KVKK compliance."
  type        = string
  default     = "eu-frankfurt-1"
}

variable "compartment_ocid" {
  description = "OCID of the compartment to deploy into (root compartment = tenancy_ocid)."
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key injected into the deploy user. Used for initial bootstrap only; remove the SSH ingress rule once the Cloudflare Tunnel is running."
  type        = string
}

variable "availability_domain_index" {
  description = "0-based index into the list of ADs returned for the region. If you get 'Out of host capacity', increment and re-apply. Frankfurt has 3 ADs (0, 1, 2)."
  type        = number
  default     = 0
}

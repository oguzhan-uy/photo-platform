terraform {
  required_version = ">= 1.7"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 6.0"
    }
  }

  # Uncomment one of the following backends for remote state.
  #
  # Option A — Terraform Cloud free tier (recommended):
  # backend "remote" {
  #   organization = "<your-tf-org>"
  #   workspaces { name = "photo-platform" }
  # }
  #
  # Option B — Cloudflare R2 (S3-compatible):
  # backend "s3" {
  #   bucket                      = "<your-r2-bucket>"
  #   key                         = "terraform/photo-platform.tfstate"
  #   region                      = "auto"
  #   endpoint                    = "https://<account-id>.r2.cloudflarestorage.com"
  #   access_key                  = "<r2-access-key>"
  #   secret_key                  = "<r2-secret-key>"
  #   skip_credentials_validation = true
  #   skip_metadata_api_check     = true
  #   skip_region_validation      = true
  #   force_path_style            = true
  # }
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

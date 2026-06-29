locals {
  name_prefix = "photo-platform"
}

# ---------- data sources ----------

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

# Latest Ubuntu 24.04 aarch64 platform image.
# OCI platform images are pre-installed in the region; no copy needed.
data "oci_core_images" "ubuntu_arm" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

# Primary VNIC for the instance — needed to attach the reserved public IP.
data "oci_core_vnic_attachments" "main" {
  compartment_id = var.compartment_ocid
  instance_id    = oci_core_instance.main.id
  depends_on     = [oci_core_instance.main]
}

data "oci_core_private_ips" "main" {
  vnic_id    = data.oci_core_vnic_attachments.main.vnic_attachments[0].vnic_id
  depends_on = [data.oci_core_vnic_attachments.main]
}

# ---------- VCN ----------

resource "oci_core_vcn" "main" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = ["10.0.0.0/16"]
  display_name   = "${local.name_prefix}-vcn"
  dns_label      = "photovn"
}

resource "oci_core_internet_gateway" "main" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${local.name_prefix}-igw"
  enabled        = true
}

resource "oci_core_default_route_table" "main" {
  manage_default_resource_id = oci_core_vcn.main.default_route_table_id

  route_rules {
    destination       = "0.0.0.0/0"
    network_entity_id = oci_core_internet_gateway.main.id
  }
}

# ---------- security list — egress-only ----------
#
# The host exposes zero inbound ports to the internet; all client traffic
# arrives via the Cloudflare Tunnel (outbound-only connection from cloudflared).
# SSH ingress on port 22 is included for initial bootstrap only.
# AFTER the tunnel is running and you have verified cloudflared access,
# remove the SSH rule and re-apply to close the final inbound port.

resource "oci_core_security_list" "egress_only" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "${local.name_prefix}-egress-only"

  # All outbound traffic: apt updates, R2 uploads, Cloudflare Tunnel, GHCR pulls.
  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
    description = "All egress — required for cloudflared, R2, GHCR, apt."
  }

  # SSH for initial bootstrap. Restrict to your IP in production.
  # Remove this rule entirely once the Cloudflare Tunnel is established.
  ingress_security_rules {
    protocol    = "6" # TCP
    source      = "0.0.0.0/0"
    description = "SSH — bootstrap only. Restrict to your IP and remove after tunnel is up."
    tcp_options {
      min = 22
      max = 22
    }
  }
}

# ---------- subnet ----------

resource "oci_core_subnet" "main" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.main.id
  cidr_block        = "10.0.1.0/24"
  display_name      = "${local.name_prefix}-subnet"
  dns_label         = "photosn"
  security_list_ids = [oci_core_security_list.egress_only.id]
  route_table_id    = oci_core_vcn.main.default_route_table_id
}

# ---------- A1 ARM instance ----------

resource "oci_core_instance" "main" {
  compartment_id = var.compartment_ocid

  # If you get "Out of host capacity", increment availability_domain_index and re-apply.
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[
    var.availability_domain_index
  ].name

  display_name = local.name_prefix
  shape        = "VM.Standard.A1.Flex"

  shape_config {
    # Always Free quota: 4 OCPU + 24 GB is the maximum for A1 in a tenancy.
    ocpus         = 4
    memory_in_gbs = 24
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu_arm.images[0].id
    boot_volume_size_in_gbs = 200
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.main.id
    display_name     = "${local.name_prefix}-vnic"
    assign_public_ip = false # reserved IP is attached below
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(
      templatefile("${path.module}/../cloud-init/bootstrap.yaml", {
        ssh_public_key = var.ssh_public_key
      })
    )
  }

  lifecycle {
    # Don't re-run cloud-init or swap images on minor config changes.
    ignore_changes = [
      metadata["user_data"],
      source_details[0].source_id,
    ]
  }
}

# ---------- reserved public IP ----------
#
# Reserved IPs survive instance stop/start and termination+rebuild,
# keeping the Cloudflare Tunnel DNS record stable.

resource "oci_core_public_ip" "main" {
  compartment_id = var.compartment_ocid
  lifetime       = "RESERVED"
  display_name   = "${local.name_prefix}-ip"
  private_ip_id  = data.oci_core_private_ips.main.private_ips[0].id

  lifecycle {
    # Ignore private_ip_id drift — detach/reattach would cause downtime.
    ignore_changes = [private_ip_id]
  }
}

output "instance_public_ip" {
  description = "Reserved public IP of the A1 instance. Point your Cloudflare Tunnel DNS here."
  value       = oci_core_public_ip.main.ip_address
}

output "instance_id" {
  description = "OCID of the A1 instance."
  value       = oci_core_instance.main.id
}

output "ssh_command" {
  description = "SSH command for initial bootstrap (before the tunnel replaces it)."
  value       = "ssh -i <your-private-key> ubuntu@${oci_core_public_ip.main.ip_address}"
}

output "capacity_block_reservation_id" {
  description = "Capacity Block reservation ID. Cannot be cancelled — billing runs to the end of the window regardless of instance state."
  value       = aws_ec2_capacity_block_reservation.gpu.id
}

output "capacity_block_offering_id" {
  description = "The matched offering. Re-run `terraform plan` to re-resolve if the reservation window lapses."
  value       = data.aws_ec2_capacity_block_offering.gpu.capacity_block_offering_id
}

output "instance_ids" {
  description = "Launched GPU node instance IDs."
  value       = aws_instance.gpu[*].id
}

output "instance_private_ips" {
  description = "Primary private IP per node (the ENA interface, card 0 device 0)."
  value       = aws_instance.gpu[*].private_ip
}

output "efa_device_count_per_node" {
  description = "EFA-only interfaces attached per node. Should be 32 for full-bandwidth p5e/p5en."
  value       = length([for i in local.efa_interfaces : i if i.type == "efa-only"])
}

output "node_hardware" {
  description = "Per-node accelerator and host capacity, for capacity-planning and cost-per-token accounting."
  value = {
    instance_type   = var.instance_type
    gpus_per_node   = 8
    gpu_model       = "NVIDIA H200"
    gpu_memory_gib  = 141
    hbm_total_gib   = 1128
    host_memory_gib = 2048
    vcpus           = 192
    local_nvme_tib  = 30.4
    nvswitch_gbps   = 900
    efa_gbps        = 3200
  }
}

output "estimated_hourly_cost_usd" {
  description = <<-EOT
    Effective Capacity Block rate for the whole cluster, from the published
    Oct 2026 per-instance-hour rate. Advisory: AWS revises these rates without
    notice, so reconcile against the live pricing page before committing
    budget. p5e = $47.76/hr, p5en = $54.92/hr (US).
  EOT
  value = var.instance_count * (
    var.instance_type == "p5e.48xlarge" ? 47.76 : 54.92
  )
}

output "estimated_window_cost_usd" {
  description = "Up-front cost of the reservation window at the published rate."
  value = var.instance_count * var.capacity_duration_hours * (
    var.instance_type == "p5e.48xlarge" ? 47.76 : 54.92
  )
}

output "fsx_lustre_dns_name" {
  description = "FSx for Lustre mount target. Mount as: mount -t lustre <dns>@tcp:/<mount_name> /mnt/fsx"
  value       = var.enable_fsx_lustre ? aws_fsx_lustre_file_system.gpu[0].dns_name : null
}

output "fsx_lustre_mount_name" {
  description = "FSx for Lustre mount name."
  value       = var.enable_fsx_lustre ? aws_fsx_lustre_file_system.gpu[0].mount_name : null
}

output "rollout_archive_bucket" {
  description = "S3 bucket holding archived agent trajectories and checkpoints."
  value       = aws_s3_bucket.rollout_archive.id
}

output "node_instance_profile" {
  description = "Instance profile attached to GPU nodes."
  value       = aws_iam_instance_profile.gpu_node.name
}

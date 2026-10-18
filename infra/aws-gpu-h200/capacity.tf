# =============================================================================
# Capacity Block for ML — the reservation that makes 8x H200 obtainable
# =============================================================================
# On-demand p5e.48xlarge is effectively unavailable (AWS lists "Contact AWS"
# rather than a public rate). Capacity Blocks are the supported path: you
# reserve accelerator capacity for a fixed window and pay up front.
#
# COST — read before applying.
#   p5e.48xlarge  = $47.76 per instance-hour  ($5.97 per H200-hour)   [Oct 2026]
#   p5en.48xlarge = $54.92 US / $49.93 EU-AP  ($6.87 / $6.24 per GPU-hour)
#
#   AWS raised Capacity Block pricing ~15% in Jan 2026 and again later in the
#   year. p5e went $34.61 -> $39.80 -> $47.76. Any figure quoted from 2025 or
#   early 2026 is stale by 30-40%; re-read the live pricing page before
#   budgeting.
#
#   1 node x 24h  = $1,146.24
#   4 nodes x 7d  = $32,094.72
#   8 nodes x 30d = $275,097.60
#
# A reservation CANNOT be cancelled. `terraform destroy` removes it from state
# only; billing continues to the end of the booked window.

data "aws_ec2_capacity_block_offering" "gpu" {
  instance_type           = var.instance_type
  instance_count          = var.instance_count
  capacity_duration_hours = var.capacity_duration_hours
  start_date_range        = var.reservation_start_date_range
  end_date_range          = var.reservation_end_date_range
}

resource "aws_ec2_capacity_block_reservation" "gpu" {
  capacity_block_offering_id = data.aws_ec2_capacity_block_offering.gpu.capacity_block_offering_id
  instance_platform          = "Linux/UNIX"

  lifecycle {
    # Deliberate: destroying this resource does NOT release the capacity or
    # stop the billing. Requiring an explicit state rm makes the loss visible.
    prevent_destroy = var.prevent_capacity_block_destroy
  }

  tags = {
    Name     = "${var.name_prefix}-capacity-block"
    Duration = "${var.capacity_duration_hours}h"
  }
}

# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------
# A cluster placement group pins every node into one low-latency network
# fabric, which is what makes 3,200 Gbps EFA and 900 GB/s NVSwitch actually
# usable across nodes. Spreading the cluster across placement groups silently
# destroys collective throughput.

resource "aws_placement_group" "gpu" {
  name     = "${var.name_prefix}-cluster"
  strategy = "cluster"

  tags = { Name = "${var.name_prefix}-placement" }
}

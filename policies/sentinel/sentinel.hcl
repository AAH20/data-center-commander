# Policy set configuration.
#
# Enforcement levels here are advisory ON PURPOSE. This policy set cannot gate a
# real run in this repository: Sentinel enforcement lives in HCP Terraform and
# Terraform Enterprise paid tiers, and this repo's pipeline runs OpenTofu, which
# Sentinel does not support. The rules below are therefore the specification, and
# policies/rego/ is the executable mirror that actually gates the pipeline.

policy "data-center-governance" {
  source            = "./data-center-governance.sentinel"
  enforcement_level = "advisory"
}

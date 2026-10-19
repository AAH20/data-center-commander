# tfplan_governance.rego — executable mirror of the Sentinel specification
#
# policies/sentinel/data-center-governance.sentinel is the SPECIFICATION for four
# infrastructure contracts. It cannot gate this repository: Sentinel enforcement
# requires HCP Terraform or Terraform Enterprise paid tiers and does not run on
# OpenTofu, which is what this pipeline uses. This file is the mirror that actually
# runs, via Conftest, against `terraform show -json` output.
#
# Keep the four rules below in step with the Sentinel file.
#
# WHY THIS FILE EXISTS SEPARATELY from the other policies here. resource_tagging.rego,
# encryption.rego and friends read a NORMALISED input shape (input.resource_id,
# input.encryption.at_rest, input.tags). Nothing in this repository produces that
# shape, so Conftest fed them raw plan JSON and every rule reported SUCCESS without
# evaluating anything. These rules read the plan shape directly:
#
#   input.resource_changes[].type
#   input.resource_changes[].change.actions
#   input.resource_changes[].change.after
#
# so they fire on real plans.

package datacenter.tfplan_governance

# --- The four contracts, identical in intent to the Sentinel policy -------------

mandatory_tags := {"owner", "Environment", "team"}

encryption_attributes := {
	"aws_db_instance": "storage_encrypted",
	"aws_ebs_volume": "encrypted",
}

admin_ports := {22, 3389}

retention_floor := 7

# --- Helpers -------------------------------------------------------------------

# Resources the plan will create. Updates are excluded: an existing resource is not
# made compliant by this plan, and failing it here would block unrelated changes.
creations contains rc if {
	some rc in input.resource_changes
	"create" in rc.change.actions
}

# object.get with a default is the whole helper -- no else clause needed, and
# Rego v1 does not allow one on a function anyway.
tags_of(rc) := object.get(rc.change.after, "tags", {})

# --- 1. Mandatory accountability tags ------------------------------------------

deny contains msg if {
	some rc in creations
	missing := {tag | some tag in mandatory_tags; not tag in object.keys(tags_of(rc))}
	count(missing) > 0
	msg := sprintf("%s '%s' is missing mandatory tag(s): %v", [rc.type, rc.address, sort(missing)])
}

# --- 2. Encryption at rest -----------------------------------------------------

deny contains msg if {
	some rc in creations
	attr := encryption_attributes[rc.type]
	not object.get(rc.change.after, attr, false) == true
	msg := sprintf("%s '%s' must set %s = true", [rc.type, rc.address, attr])
}

# --- 3. No public administrative ingress ---------------------------------------

deny contains msg if {
	some rc in creations
	rc.type == "aws_security_group"
	some rule in object.get(rc.change.after, "ingress", [])
	"0.0.0.0/0" in object.get(rule, "cidr_blocks", [])
	port := object.get(rule, "from_port", 0)
	port in admin_ports
	msg := sprintf("aws_security_group '%s' exposes port %d to 0.0.0.0/0", [rc.address, port])
}

deny contains msg if {
	some rc in creations
	rc.type == "aws_security_group"
	some rule in object.get(rc.change.after, "ingress", [])
	"0.0.0.0/0" in object.get(rule, "cidr_blocks", [])
	port := object.get(rule, "to_port", 0)
	port in admin_ports
	msg := sprintf("aws_security_group '%s' exposes port %d to 0.0.0.0/0", [rc.address, port])
}

# --- 4. Retention floor for stateful services ----------------------------------

deny contains msg if {
	some rc in creations
	rc.type == "aws_db_instance"
	retention := object.get(rc.change.after, "backup_retention_period", 0)
	retention < retention_floor
	msg := sprintf("aws_db_instance '%s' has backup_retention_period %d, below the floor of %d", [rc.address, retention, retention_floor])
}

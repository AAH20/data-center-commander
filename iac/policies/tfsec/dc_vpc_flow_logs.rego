# Data Center Custom Rule: VPC Flow Logs
# Ensures all VPCs have flow logs enabled for network traffic monitoring
package custom.aws.vpc.flow_logs

import data.lib.result

# Rule: aws_vpc must have an associated aws_flow_log resource
deny[res] {
	vpc := input.aws.vpc[_]
	not vpc_flow_log_exists(vpc)
	msg := "VPC does not have flow logs enabled. Data center policy requires all VPCs to have flow logs for network monitoring."
	res := result.new(msg, vpc)
}

vpc_flow_log_exists(vpc) {
	flow_log := input.aws.flowlog[_]
	flow_log.vpc_id.value == vpc.id.value
}

# Rule: Flow log retention must be at least 90 days
deny[res] {
	flow_log := input.aws.flowlog[_]
	flow_log.log_destination_type.value == "cloud-watch-logs"
	log_group := input.aws.cloudwatch.loggroup[_]
	log_group.name.value == flow_log.log_destination.value
	log_group.retention_in_days.value < 90
	msg := "Flow log CloudWatch log group retention is less than 90 days. Data center policy requires minimum 90-day retention."
	res := result.new(msg, log_group)
}

# Rule: Flow log traffic type should be ALL for complete visibility
warn[res] {
	flow_log := input.aws.flowlog[_]
	flow_log.traffic_type.value != "ALL"
	msg := "Flow log traffic type is not ALL. Data center policy recommends capturing all traffic (ACCEPT and REJECT) for complete network visibility."
	res := result.new(msg, flow_log)
}

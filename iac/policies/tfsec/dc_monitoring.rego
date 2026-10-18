# Data Center Custom Rule: Monitoring and Logging
# Ensures data center resources have proper monitoring and logging configured
package custom.aws.monitoring

import data.lib.result

# Rule: AWS VPC flow logs must deliver to CloudWatch
deny[res] {
	flow_log := input.aws.flowlog[_]
	flow_log.log_destination_type.value != "cloud-watch-logs"
	msg := "VPC flow log does not deliver to CloudWatch Logs. Data center policy requires flow logs to be stored in CloudWatch for centralized monitoring."
	res := result.new(msg, flow_log)
}

# Rule: AWS CloudWatch log groups must have retention set
deny[res] {
	log_group := input.aws.cloudwatch.loggroup[_]
	not log_group.retention_in_days
	msg := "CloudWatch log group does not have retention policy set. Data center policy requires retention to be explicitly configured."
	res := result.new(msg, log_group)
}

# Rule: AWS Config delivery channel must have SNS topic for notifications
warn[res] {
	channel := input.aws.config.deliverychannel[_]
	not channel.sns_topic_arn
	msg := "AWS Config delivery channel does not have SNS topic configured. Data center policy recommends SNS notifications for configuration changes."
	res := result.new(msg, channel)
}

# Rule: KVM domains should have console access configured for troubleshooting
warn[res] {
	domain := input.libvirt.domain[_]
	not domain.console
	msg := "KVM domain does not have console configured. Data center policy recommends serial console access for troubleshooting."
	res := result.new(msg, domain)
}

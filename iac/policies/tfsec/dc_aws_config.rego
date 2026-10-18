# Data Center Custom Rule: AWS Config Compliance
# Ensures AWS Config is properly enabled and configured for compliance monitoring
package custom.aws.config.compliance

import data.lib.result

# Rule: AWS Config configuration recorder must exist
deny[res] {
	not input.aws.config.configurationrecorder
	msg := "No AWS Config configuration recorder found. Data center policy requires AWS Config to be enabled for compliance monitoring."
	res := result.new(msg, "")
}

# Rule: AWS Config recorder must be enabled
deny[res] {
	recorder := input.aws.config.configurationrecorderstatus[_]
	recorder.is_enabled.value == false
	msg := "AWS Config configuration recorder is not enabled. Data center policy requires the recorder to be active."
	res := result.new(msg, recorder)
}

# Rule: AWS Config delivery channel must exist
deny[res] {
	not input.aws.config.deliverychannel
	msg := "No AWS Config delivery channel found. Data center policy requires a delivery channel for configuration snapshots."
	res := result.new(msg, "")
}

# Rule: AWS Config recording frequency should be at most 6 hours
warn[res] {
	channel := input.aws.config.deliverychannel[_]
	channel.snapshot_delivery_properties.delivery_frequency.value == "TwentyFour_Hours"
	msg := "AWS Config delivery frequency is 24 hours. Data center policy recommends 6 hours or less for near-real-time compliance monitoring."
	res := result.new(msg, channel)
}

# Rule: AWS Config should record all supported resources
warn[res] {
	recorder := input.aws.config.configurationrecorder[_]
	recorder.recording_group.all_supported.value == false
	msg := "AWS Config is not recording all supported resource types. Data center policy recommends recording all supported resources."
	res := result.new(msg, recorder)
}

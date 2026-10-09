#!/bin/bash
# SOC Alert Handler — Data Center Commander
# Version: 1.0.0
# Description: Handles security alerts from Trivy and OPA, routes to appropriate channels

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
PAGERDUTY_KEY="${PAGERDUTY_KEY:-}"
EMAIL_SMTP="${EMAIL_SMTP:-}"
ALERT_LOG="/var/log/soc/alerts.log"
OPA_URL="${OPA_URL:-http://opa.opa.svc.cluster.local:8181}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# =============================================================================
# FUNCTIONS
# =============================================================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "${ALERT_LOG}"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "${ALERT_LOG}"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "${ALERT_LOG"
}

# Send Slack notification
send_slack() {
    local severity="$1"
    local message="$2"
    local color="danger"

    case "${severity}" in
        CRITICAL) color="danger" ;;
        HIGH) color="warning" ;;
        MEDIUM) color="#439FE0" ;;
        LOW) color="good" ;;
    esac

    if [ -n "${SLACK_WEBHOOK_URL}" ]; then
        curl -s -X POST \
            -H "Content-Type: application/json" \
            -d "{
                \"text\": \"DCC SOC Alert\",
                \"attachments\": [{
                    \"color\": \"${color}\",
                    \"fields\": [
                        {\"title\": \"Severity\", \"value\": \"${severity}\", \"short\": true},
                        {\"title\": \"Message\", \"value\": \"${message}\", \"short\": false}
                    ]
                }]
            }" \
            "${SLACK_WEBHOOK_URL}" > /dev/null 2>&1 || log_warn "Failed to send Slack notification"
    fi
}

# Send PagerDuty alert
send_pagerduty() {
    local severity="$1"
    local message="$2"
    local dedup_key="$3"

    if [ -n "${PAGERDUTY_KEY}" ]; then
        curl -s -X POST \
            -H "Content-Type: application/json" \
            -d "{
                \"routing_key\": \"${PAGERDUTY_KEY}\",
                \"event_action\": \"trigger\",
                \"dedup_key\": \"${dedup_key}\",
                \"payload\": {
                    \"summary\": \"${message}\",
                    \"severity\": \"${severity,,}\",
                    \"source\": \"DCC SOC\",
                    \"component\": \"Container Security\",
                    \"group\": \"Security\",
                    \"class\": \"Security Alert\"
                }
            }" \
            "https://events.pagerduty.com/v2/enqueue" > /dev/null 2>&1 || log_warn "Failed to send PagerDuty alert"
    fi
}

# Send email notification
send_email() {
    local severity="$1"
    local message="$2"
    local to="${3:-soc@data-center-commander.local}"

    if [ -n "${EMAIL_SMTP}" ]; then
        echo "${message}" | mail -s "[DCC SOC] ${severity} Security Alert" \
            -S smtp="${EMAIL_SMTP}" \
            "${to}" 2>/dev/null || log_warn "Failed to send email notification"
    fi
}

# Evaluate alert with OPA
evaluate_with_opa() {
    local alert_data="$1"

    local opa_response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "{\"input\": ${alert_data}}" \
        "${OPA_URL}/v1/data/soc" 2>&1)

    echo "${opa_response}"
}

# Handle Trivy vulnerability alert
handle_trivy_alert() {
    local report_file="$1"

    log_info "Handling Trivy alert from: ${report_file}"

    # Extract vulnerability counts
    local critical=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL")] | length' "${report_file}" 2>/dev/null || echo "0")
    local high=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH")] | length' "${report_file}" 2>/dev/null || echo "0")
    local medium=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "MEDIUM")] | length' "${report_file}" 2>/dev/null || echo "0")
    local low=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "LOW")] | length' "${report_file}" 2>/dev/null || echo "0")

    local image=$(jq -r '.ArtifactName' "${report_file}" 2>/dev/null || echo "unknown")

    # Determine severity
    local severity="LOW"
    if [ "${critical}" -gt 0 ]; then
        severity="CRITICAL"
    elif [ "${high}" -gt 0 ]; then
        severity="HIGH"
    elif [ "${medium}" -gt 0 ]; then
        severity="MEDIUM"
    fi

    local message="Trivy scan for ${image}: ${critical} critical, ${high} high, ${medium} medium, ${low} low vulnerabilities"

    log_info "Alert severity: ${severity}"
    log_info "Message: ${message}"

    # Send notifications
    send_slack "${severity}" "${message}"

    if [ "${severity}" == "CRITICAL" ] || [ "${severity}" == "HIGH" ]; then
        send_pagerduty "${severity}" "${message}" "trivy-${image}"
    fi

    if [ "${severity}" == "CRITICAL" ]; then
        send_email "${severity}" "${message}"
    fi

    # Evaluate with OPA
    local opa_input=$(jq -n \
        --arg image "${image}" \
        --argjson critical "${critical}" \
        --argjson high "${high}" \
        --argjson medium "${medium}" \
        --argjson low "${low}" \
        '{
            input: {
                event_type: "vulnerability",
                image: $image,
                severity: (if $critical > 0 then "CRITICAL" elif $high > 0 then "HIGH" elif $medium > 0 then "MEDIUM" else "LOW" end),
                vulnerabilities: {
                    critical: $critical,
                    high: $high,
                    medium: $medium,
                    low: $low
                }
            }
        }')

    evaluate_with_opa "${opa_input}"
}

# Handle OPA policy violation alert
handle_opa_alert() {
    local violation_data="$1"

    log_info "Handling OPA policy violation alert"

    local violations=$(echo "${violation_data}" | jq -r '.violations // []' 2>/dev/null || echo "[]")
    local image=$(echo "${violation_data}" | jq -r '.image // "unknown"' 2>/dev/null || echo "unknown")

    local message="OPA policy violation for ${image}: ${violations}"

    log_info "Message: ${message}"

    send_slack "HIGH" "${message}"
    send_pagerduty "HIGH" "${message}" "opa-${image}"
}

# Handle autoscaling security alert
handle_autoscaling_alert() {
    local alert_data="$1"

    log_info "Handling autoscaling security alert"

    local message=$(echo "${alert_data}" | jq -r '.message // "Autoscaling security alert"' 2>/dev/null || echo "Autoscaling security alert")

    send_slack "MEDIUM" "${message}"
}

# =============================================================================
# MAIN
# =============================================================================
main() {
    local alert_type="${1:-}"
    local alert_data="${2:-}"

    mkdir -p "$(dirname "${ALERT_LOG}")"

    log_info "=========================================="
    log_info "SOC Alert Handler"
    log_info "=========================================="

    case "${alert_type}" in
        trivy)
            handle_trivy_alert "${alert_data}"
            ;;
        opa)
            handle_opa_alert "${alert_data}"
            ;;
        autoscaling)
            handle_autoscaling_alert "${alert_data}"
            ;;
        *)
            log_error "Unknown alert type: ${alert_type}"
            log_info "Usage: $0 [trivy|opa|autoscaling] [data]"
            exit 1
            ;;
    esac

    log_info "Alert handling completed"
}

main "$@"

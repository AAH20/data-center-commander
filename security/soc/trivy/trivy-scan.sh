#!/bin/bash
# Trivy Scan Script — Data Center Commander SOC
# Version: 2.0.0
# Description: Comprehensive container security scanning with Trivy + OPA integration

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/trivy-config.yaml"
REPORT_DIR="/var/log/trivy"
OPA_URL="${OPA_URL:-http://opa.opa.svc.cluster.local:8181}"
OPA_POLICY_PATH="${OPA_POLICY_PATH:-/v1/data/container-security}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
NAMESPACE="${NAMESPACE:-data-center-commander}"
IMAGE="${1:-}"
SCAN_TYPE="${2:-full}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# FUNCTIONS
# =============================================================================
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Check if Trivy is installed
check_trivy() {
    if ! command -v trivy &> /dev/null; then
        log_error "Trivy is not installed. Please install Trivy first."
        log_info "Install with: brew install trivy"
        exit 1
    fi
    log_info "Trivy version: $(trivy --version)"
}

# Check if OPA is accessible
check_opa() {
    if ! curl -s -o /dev/null -w "%{http_code}" "${OPA_URL}/health" | grep -q "200"; then
        log_warn "OPA server not accessible at ${OPA_URL}"
        return 1
    fi
    log_info "OPA server accessible at ${OPA_URL}"
    return 0
}

# Scan container image
scan_image() {
    local image="$1"
    local scan_type="$2"
    local report_file="${REPORT_DIR}/trivy-report-$(date +%Y%m%d-%H%M%S).json"

    log_info "Starting Trivy scan for image: ${image}"
    log_info "Scan type: ${scan_type}"

    # Create report directory
    mkdir -p "${REPORT_DIR}"

    # Run Trivy scan
    trivy image \
        --severity CRITICAL,HIGH,MEDIUM,LOW \
        --scanners vuln,secret,config,license \
        --format json \
        --output "${report_file}" \
        --timeout 10m \
        --cache-dir /tmp/trivy-cache \
        --offline-scan \
        "${image}" 2>&1 | tee "${REPORT_DIR}/trivy-scan.log"

    local exit_code=${PIPESTATUS[0]}

    if [ ${exit_code} -ne 0 ]; then
        log_error "Trivy scan failed with exit code ${exit_code}"
        return ${exit_code}
    fi

    log_success "Trivy scan completed. Report: ${report_file}"

    # Parse results
    parse_results "${report_file}"

    # Evaluate with OPA
    evaluate_with_opa "${report_file}" "${image}"

    # Send notifications
    send_notifications "${report_file}" "${image}"

    return 0
}

# Parse Trivy scan results
parse_results() {
    local report_file="$1"

    log_info "Parsing scan results..."

    # Extract vulnerability counts
    local critical=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL")] | length' "${report_file}" 2>/dev/null || echo "0")
    local high=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH")] | length' "${report_file}" 2>/dev/null || echo "0")
    local medium=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "MEDIUM")] | length' "${report_file}" 2>/dev/null || echo "0")
    local low=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "LOW")] | length' "${report_file}" 2>/dev/null || echo "0")

    log_info "Vulnerability Summary:"
    log_info "  CRITICAL: ${critical}"
    log_info "  HIGH: ${high}"
    log_info "  MEDIUM: ${medium}"
    log_info "  LOW: ${low}"

    # Extract misconfigurations
    local misconfigs=$(jq '[.Results[]?.Misconfigurations[]?] | length' "${report_file}" 2>/dev/null || echo "0")
    log_info "Misconfigurations: ${misconfigs}"

    # Extract secrets
    local secrets=$(jq '[.Results[]?.Secrets[]?] | length' "${report_file}" 2>/dev/null || echo "0")
    log_info "Secrets found: ${secrets}"

    # Export for OPA evaluation
    export TRIVY_CRITICAL="${critical}"
    export TRIVY_HIGH="${high}"
    export TRIVY_MEDIUM="${medium}"
    export TRIVY_LOW="${low}"
    export TRIVY_MISCONFIGS="${misconfigs}"
    export TRIVY_SECRETS="${secrets}"
}

# Evaluate scan results with OPA
evaluate_with_opa() {
    local report_file="$1"
    local image="$2"

    log_info "Evaluating with OPA..."

    # Prepare OPA input
    local opa_input=$(jq -n \
        --arg image "${image}" \
        --argjson critical "${TRIVY_CRITICAL:-0}" \
        --argjson high "${TRIVY_HIGH:-0}" \
        --argjson medium "${TRIVY_MEDIUM:-0}" \
        --argjson low "${TRIVY_LOW:-0}" \
        --argjson misconfigs "${TRIVY_MISCONFIGS:-0}" \
        --argjson secrets "${TRIVY_SECRETS:-0}" \
        '{
            input: {
                image: $image,
                vulnerabilities: {
                    critical: $critical,
                    high: $high,
                    medium: $medium,
                    low: $low
                },
                misconfigurations: $misconfigs,
                secrets: $secrets,
                timestamp: now | todate
            }
        }')

    # Send to OPA for evaluation
    local opa_response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "${opa_input}" \
        "${OPA_URL}${OPA_POLICY_PATH}" 2>&1)

    log_info "OPA Response: ${opa_response}"

    # Parse OPA response
    local allowed=$(echo "${opa_response}" | jq -r '.result.allow // "unknown"' 2>/dev/null || echo "unknown")
    local violations=$(echo "${opa_response}" | jq -r '.result.violations // []' 2>/dev/null || echo "[]")

    if [ "${allowed}" == "true" ]; then
        log_success "OPA evaluation: ALLOWED"
    else
        log_error "OPA evaluation: DENIED"
        log_error "Violations: ${violations}"
    fi

    # Save OPA evaluation
    echo "${opa_response}" > "${REPORT_DIR}/opa-evaluation-$(date +%Y%m%d-%H%M%S).json"

    return 0
}

# Send notifications
send_notifications() {
    local report_file="$1"
    local image="$2"

    log_info "Sending notifications..."

    # Slack notification
    if [ -n "${SLACK_WEBHOOK_URL}" ]; then
        local slack_message=$(jq -n \
            --arg image "${image}" \
            --argjson critical "${TRIVY_CRITICAL:-0}" \
            --argjson high "${TRIVY_HIGH:-0}" \
            --argjson medium "${TRIVY_MEDIUM:-0}" \
            --argjson low "${TRIVY_LOW:-0}" \
            '{
                text: "Trivy Scan Complete",
                attachments: [{
                    color: (if ($critical | tonumber) > 0 then "danger" elif ($high | tonumber) > 0 then "warning" else "good" end),
                    fields: [
                        {title: "Image", value: $image, short: true},
                        {title: "Critical", value: ($critical | tostring), short: true},
                        {title: "High", value: ($high | tostring), short: true},
                        {title: "Medium", value: ($medium | tostring), short: true},
                        {title: "Low", value: ($low | tostring), short: true}
                    ]
                }]
            }')

        curl -s -X POST \
            -H "Content-Type: application/json" \
            -d "${slack_message}" \
            "${SLACK_WEBHOOK_URL}" > /dev/null 2>&1 || log_warn "Failed to send Slack notification"
    fi

    # Webhook notification
    if [ -n "${WEBHOOK_URL:-}" ]; then
        curl -s -X POST \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer ${WEBHOOK_TOKEN:-}" \
            -d @"${report_file}" \
            "${WEBHOOK_URL}" > /dev/null 2>&1 || log_warn "Failed to send webhook notification"
    fi
}

# Scan Kubernetes cluster
scan_kubernetes() {
    log_info "Starting Trivy Kubernetes scan..."

    local report_file="${REPORT_DIR}/trivy-k8s-report-$(date +%Y%m%d-%H%M%S).json"

    trivy k8s \
        --severity CRITICAL,HIGH,MEDIUM,LOW \
        --scanners vuln,secret,config \
        --format json \
        --output "${report_file}" \
        --timeout 10m \
        --cache-dir /tmp/trivy-cache \
        --namespace "${NAMESPACE}" \
        --report summary \
        cluster 2>&1 | tee "${REPORT_DIR}/trivy-k8s-scan.log"

    local exit_code=${PIPESTATUS[0]}

    if [ ${exit_code} -ne 0 ]; then
        log_error "Trivy K8s scan failed with exit code ${exit_code}"
        return ${exit_code}
    fi

    log_success "Trivy K8s scan completed. Report: ${report_file}"

    # Parse results
    parse_results "${report_file}"

    # Evaluate with OPA
    evaluate_with_opa "${report_file}" "k8s-cluster"

    return 0
}

# Scan filesystem
scan_filesystem() {
    local target="${1:-.}"

    log_info "Starting Trivy filesystem scan for: ${target}"

    local report_file="${REPORT_DIR}/trivy-fs-report-$(date +%Y%m%d-%H%M%S).json"

    trivy fs \
        --severity CRITICAL,HIGH,MEDIUM,LOW \
        --scanners vuln,secret,config,license \
        --format json \
        --output "${report_file}" \
        --timeout 10m \
        --cache-dir /tmp/trivy-cache \
        "${target}" 2>&1 | tee "${REPORT_DIR}/trivy-fs-scan.log"

    local exit_code=${PIPESTATUS[0]}

    if [ ${exit_code} -ne 0 ]; then
        log_error "Trivy filesystem scan failed with exit code ${exit_code}"
        return ${exit_code}
    fi

    log_success "Trivy filesystem scan completed. Report: ${report_file}"

    # Parse results
    parse_results "${report_file}"

    return 0
}

# Scan Dockerfile
scan_dockerfile() {
    local dockerfile="${1:-Dockerfile}"

    log_info "Starting Trivy Dockerfile scan for: ${dockerfile}"

    local report_file="${REPORT_DIR}/trivy-dockerfile-report-$(date +%Y%m%d-%H%M%S).json"

    trivy config \
        --severity CRITICAL,HIGH,MEDIUM,LOW \
        --format json \
        --output "${report_file}" \
        --timeout 10m \
        "${dockerfile}" 2>&1 | tee "${REPORT_DIR}/trivy-dockerfile-scan.log"

    local exit_code=${PIPESTATUS[0]}

    if [ ${exit_code} -ne 0 ]; then
        log_error "Trivy Dockerfile scan failed with exit code ${exit_code}"
        return ${exit_code}
    fi

    log_success "Trivy Dockerfile scan completed. Report: ${report_file}"

    return 0
}

# Generate compliance report
generate_compliance_report() {
    log_info "Generating compliance report..."

    local report_file="${REPORT_DIR}/compliance-report-$(date +%Y%m%d-%H%M%S).json"

    trivy image \
        --severity CRITICAL,HIGH,MEDIUM,LOW \
        --scanners vuln,secret,config \
        --format json \
        --output "${report_file}" \
        --compliance cis-docker \
        --timeout 10m \
        "${IMAGE}" 2>&1 | tee "${REPORT_DIR}/compliance-scan.log"

    log_success "Compliance report generated: ${report_file}"
}

# =============================================================================
# MAIN
# =============================================================================
main() {
    log_info "=========================================="
    log_info "Trivy Scan Script — Data Center Commander SOC"
    log_info "=========================================="

    # Check prerequisites
    check_trivy

    # Check OPA
    check_opa || log_warn "OPA not available, skipping policy evaluation"

    # Execute scan based on type
    case "${SCAN_TYPE}" in
        image)
            if [ -z "${IMAGE}" ]; then
                log_error "Image name required for image scan"
                exit 1
            fi
            scan_image "${IMAGE}" "${SCAN_TYPE}"
            ;;
        k8s|kubernetes)
            scan_kubernetes
            ;;
        fs|filesystem)
            scan_filesystem "${IMAGE:-.}"
            ;;
        dockerfile)
            scan_dockerfile "${IMAGE:-Dockerfile}"
            ;;
        compliance)
            if [ -z "${IMAGE}" ]; then
                log_error "Image name required for compliance scan"
                exit 1
            fi
            generate_compliance_report
            ;;
        *)
            log_error "Unknown scan type: ${SCAN_TYPE}"
            log_info "Usage: $0 [image] [image|k8s|fs|dockerfile|compliance]"
            exit 1
            ;;
    esac

    log_success "Scan completed successfully"
}

# Run main
main "$@"

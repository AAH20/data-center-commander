#!/bin/bash
# OPA Policy Evaluator — Data Center Commander SOC
# Version: 1.0.0
# Description: Evaluates container security policies using OPA

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================
OPA_URL="${OPA_URL:-http://opa.opa.svc.cluster.local:8181}"
POLICY_PATH="${POLICY_PATH:-/v1/data/container-security}"
TIMEOUT="${TIMEOUT:-30}"

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

# Check OPA server health
check_opa_health() {
    local health_status=$(curl -s -o /dev/null -w "%{http_code}" "${OPA_URL}/health" 2>/dev/null || echo "000")

    if [ "${health_status}" != "200" ]; then
        log_error "OPA server not healthy at ${OPA_URL}"
        return 1
    fi

    log_info "OPA server healthy at ${OPA_URL}"
    return 0
}

# Evaluate container security policy
evaluate_container_security() {
    local input_data="$1"

    log_info "Evaluating container security policy..."

    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "{\"input\": ${input_data}}" \
        --max-time "${TIMEOUT}" \
        "${OPA_URL}${POLICY_PATH}" 2>&1)

    local exit_code=$?

    if [ ${exit_code} -ne 0 ]; then
        log_error "OPA evaluation failed with exit code ${exit_code}"
        return 1
    fi

    # Parse response
    local allowed=$(echo "${response}" | jq -r '.result.allow // "unknown"' 2>/dev/null || echo "unknown")
    local violations=$(echo "${response}" | jq -r '.result.violations // []' 2>/dev/null || echo "[]")

    log_info "OPA Evaluation Result:"
    log_info "  Allowed: ${allowed}"
    log_info "  Violations: ${violations}"

    if [ "${allowed}" == "true" ]; then
        log_success "Policy evaluation: ALLOWED"
        return 0
    else
        log_error "Policy evaluation: DENIED"
        echo "${violations}" | jq -r '.[]' | while read -r violation; do
            log_error "  - ${violation}"
        done
        return 1
    fi
}

# Evaluate autoscaling policy
evaluate_autoscaling() {
    local input_data="$1"

    log_info "Evaluating autoscaling policy..."

    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "{\"input\": ${input_data}}" \
        --max-time "${TIMEOUT}" \
        "${OPA_URL}/v1/data/autoscaling" 2>&1)

    local exit_code=$?

    if [ ${exit_code} -ne 0 ]; then
        log_error "OPA autoscaling evaluation failed with exit code ${exit_code}"
        return 1
    fi

    local allowed=$(echo "${response}" | jq -r '.result.allow // "unknown"' 2>/dev/null || echo "unknown")
    local violations=$(echo "${response}" | jq -r '.result.violations // []' 2>/dev/null || echo "[]")

    log_info "Autoscaling Evaluation Result:"
    log_info "  Allowed: ${allowed}"
    log_info "  Violations: ${violations}"

    if [ "${allowed}" == "true" ]; then
        log_success "Autoscaling policy evaluation: ALLOWED"
        return 0
    else
        log_error "Autoscaling policy evaluation: DENIED"
        return 1
    fi
}

# Evaluate SOC policy
evaluate_soc() {
    local input_data="$1"

    log_info "Evaluating SOC policy..."

    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "{\"input\": ${input_data}}" \
        --max-time "${TIMEOUT}" \
        "${OPA_URL}/v1/data/soc" 2>&1)

    local exit_code=$?

    if [ ${exit_code} -ne 0 ]; then
        log_error "OPA SOC evaluation failed with exit code ${exit_code}"
        return 1
    fi

    local alert_severity=$(echo "${response}" | jq -r '.result.alert_severity // "unknown"' 2>/dev/null || echo "unknown")
    local alert_route=$(echo "${response}" | jq -r '.result.alert_route // "unknown"' 2>/dev/null || echo "unknown")
    local auto_remediate=$(echo "${response}" | jq -r '.result.auto_remediate // "unknown"' 2>/dev/null || echo "unknown")

    log_info "SOC Evaluation Result:"
    log_info "  Alert Severity: ${alert_severity}"
    log_info "  Alert Route: ${alert_route}"
    log_info "  Auto Remediate: ${auto_remediate}"

    return 0
}

# Evaluate Trivy scan results
evaluate_trivy_scan() {
    local report_file="$1"

    log_info "Evaluating Trivy scan results from: ${report_file}"

    if [ ! -f "${report_file}" ]; then
        log_error "Report file not found: ${report_file}"
        return 1
    fi

    # Extract data from Trivy report
    local image=$(jq -r '.ArtifactName' "${report_file}" 2>/dev/null || echo "unknown")
    local critical=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL")] | length' "${report_file}" 2>/dev/null || echo "0")
    local high=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH")] | length' "${report_file}" 2>/dev/null || echo "0")
    local medium=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "MEDIUM")] | length' "${report_file}" 2>/dev/null || echo "0")
    local low=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "LOW")] | length' "${report_file}" 2>/dev/null || echo "0")
    local misconfigs=$(jq '[.Results[]?.Misconfigurations[]?] | length' "${report_file}" 2>/dev/null || echo "0")
    local secrets=$(jq '[.Results[]?.Secrets[]?] | length' "${report_file}" 2>/dev/null || echo "0")

    # Build input JSON
    local input_data=$(jq -n \
        --arg image "${image}" \
        --argjson critical "${critical}" \
        --argjson high "${high}" \
        --argjson medium "${medium}" \
        --argjson low "${low}" \
        --argjson misconfigs "${misconfigs}" \
        --argjson secrets "${secrets}" \
        '{
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
        }')

    evaluate_container_security "${input_data}"
}

# =============================================================================
# MAIN
# =============================================================================
main() {
    local command="${1:-}"
    local input_data="${2:-}"

    log_info "=========================================="
    log_info "OPA Policy Evaluator"
    log_info "=========================================="

    # Check OPA health
    check_opa_health || exit 1

    case "${command}" in
        container-security)
            evaluate_container_security "${input_data}"
            ;;
        autoscaling)
            evaluate_autoscaling "${input_data}"
            ;;
        soc)
            evaluate_soc "${input_data}"
            ;;
        trivy-scan)
            evaluate_trivy_scan "${input_data}"
            ;;
        *)
            log_error "Unknown command: ${command}"
            log_info "Usage: $0 [container-security|autoscaling|soc|trivy-scan] [data]"
            exit 1
            ;;
    esac
}

main "$@"

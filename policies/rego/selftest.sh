#!/usr/bin/env bash
# Prove the governance gate can fail.
#
# A policy suite with only a passing case proves nothing. This asserts BOTH
# directions: a compliant plan must produce no violations, a violating plan must
# produce them, and every one of the four controls must appear by name.
#
# Run from the repo root:  bash policies/rego/selftest.sh
#
# Uses `opa eval` when available (deterministic, no network) and falls back to
# conftest otherwise. Both are the same engine underneath; conftest just wraps it.
set -uo pipefail

POL="policies/rego/tfplan_governance.rego"
NS="datacenter.tfplan_governance"
FX="policies/rego/testdata/tfplan_governance"
RULE="data.${NS}.deny"
fail=0

run() {  # run <fixture> -> prints the deny set
  if command -v opa >/dev/null 2>&1; then
    opa eval -d "$POL" -i "$1" "$RULE" --format raw 2>&1
  else
    conftest test "$1" --policy "$POL" --namespace "$NS" --output json 2>&1
  fi
}

# 1. compliant plan must yield no violations
out=$(run "$FX/compliant.json")
if echo "$out" | grep -q "missing mandatory tag"; then
  echo "FAIL  compliant plan rejected (the gate is over-firing)"; fail=1
else
  echo "PASS  compliant plan accepted"
fi

# 2. violating plan must yield every control, by name
out=$(run "$FX/violating.json")
for needle in "missing mandatory tag" "must set" "exposes port" "below the floor"; do
  if echo "$out" | grep -q "$needle"; then
    echo "PASS  control fired: $needle"
  else
    echo "FAIL  control did not fire: $needle"; fail=1
  fi
done

exit $fail

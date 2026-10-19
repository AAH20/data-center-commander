#!/usr/bin/env bash
# Prove the governance gate can fail.
#
# A policy suite with only a passing case proves nothing. This asserts BOTH
# directions: a compliant plan must exit 0, a violating plan must exit non-zero
# AND must report every one of the four controls.
#
# Run from the repo root:  bash policies/rego/selftest.sh
set -uo pipefail

POLICY="policies/rego/tfplan_governance.rego"
NS="datacenter.tfplan_governance"
FIX="policies/rego/testdata/tfplan_governance"
CONFTEST="${CONFTEST:-conftest}"

fail=0

if "$CONFTEST" test "$FIX/compliant.json" --policy "$POLICY" --namespace "$NS" \
     --output json > /tmp/st-compliant.json 2>&1; then
  echo "PASS  compliant plan accepted"
else
  echo "FAIL  compliant plan was rejected (the gate is over-firing)"
  fail=1
fi

if "$CONFTEST" test "$FIX/violating.json" --policy "$POLICY" --namespace "$NS" \
     --output json > /tmp/st-violating.json 2>&1; then
  echo "FAIL  violating plan was accepted (the gate is not firing)"
  fail=1
else
  echo "PASS  violating plan rejected"
fi

# every control must be present in the output
for needle in "missing mandatory tag" "must set" "exposes port" "below the floor"; do
  if grep -q "$needle" /tmp/st-violating.json; then
    echo "PASS  control fired: $needle"
  else
    echo "FAIL  control did not fire: $needle"
    fail=1
  fi
done

exit $fail

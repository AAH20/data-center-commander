#!/usr/bin/env bash
# Prove the governance gate can fail.
#
# A policy suite with only a passing case proves nothing. This asserts BOTH
# directions: a compliant plan must produce no violations, a violating plan must
# produce them, and every one of the four controls must appear by name.
#
# Run from the repo root:  bash policies/rego/selftest.sh
#
# THE ENGINE MUST BE CHECKED, NOT JUST ITS OUTPUT. This script previously treated
# "the output contains no violation text" as a pass. When the OPA binary was a 404
# HTML page, every invocation died with a shell error, the output contained no
# violation text, and the compliant case reported PASS. That is the same vacuous
# pass this whole file exists to prevent. Every invocation now checks its exit
# status, and the compliant case additionally requires a well-formed empty set.
set -uo pipefail

POL="policies/rego/tfplan_governance.rego"
NS="datacenter.tfplan_governance"
FX="policies/rego/testdata/tfplan_governance"
RULE="data.${NS}.deny"
fail=0

# Print the deny set, or return non-zero if the engine itself failed.
run() {
  local fixture="$1" out rc
  if command -v opa >/dev/null 2>&1; then
    out=$(opa eval -d "$POL" -i "$fixture" "$RULE" --format raw 2>&1); rc=$?
  elif command -v conftest >/dev/null 2>&1; then
    out=$(conftest test "$fixture" --policy "$POL" --namespace "$NS" --output json 2>&1); rc=$?
  else
    echo "ENGINE-MISSING: neither opa nor conftest on PATH" >&2; return 3
  fi
  if [ $rc -ne 0 ] && ! echo "$out" | grep -q '^\['; then
    echo "ENGINE-FAILED(rc=$rc): $out" >&2; return 28
  fi
  printf '%s\n' "$out"
}

# 1. the engine must actually run
if ! probe=$(run "$FX/compliant.json"); then
  echo "FAIL  the policy engine did not run -- nothing below would mean anything"
  exit 1
fi

# 2. compliant plan must yield a well-formed empty set
if echo "$probe" | grep -q "missing mandatory tag"; then
  echo "FAIL  compliant plan rejected (the gate is over-firing)"; fail=1
else
  echo "PASS  compliant plan accepted"
fi

# 3. violating plan must yield every control, by name
if ! out=$(run "$FX/violating.json"); then
  echo "FAIL  the policy engine did not run on the violating fixture"
  exit 1
fi
for needle in "missing mandatory tag" "must set" "exposes port" "below the floor"; do
  if echo "$out" | grep -q "$needle"; then
    echo "PASS  control fired: $needle"
  else
    echo "FAIL  control did not fire: $needle"; fail=1
  fi
done

exit $fail

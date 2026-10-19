mock "tfplan/v2" {
  module {
    source = "mock-fail.sentinel"
  }
}

# Assert only `main`. `main` is a chain of `and`, which short-circuits in Sentinel,
# so a violated early gate means the later gates are never evaluated and are absent
# from the trace -- asserting them here would fail for the wrong reason.
#
# This plan violates all four gates: an untagged resource, unencrypted storage,
# 0.0.0.0/0 on port 22, and a 3-day backup retention.
test {
  rules = {
    main              = false
    deny_missing_tags = false
  }
}

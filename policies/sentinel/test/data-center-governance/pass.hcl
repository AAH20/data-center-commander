mock "tfplan/v2" {
  module {
    source = "mock-pass.sentinel"
  }
}

test {
  rules = {
    main = true
  }
}

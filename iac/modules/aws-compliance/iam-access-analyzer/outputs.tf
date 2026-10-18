output "analyzer_id" {
  description = "ID of the IAM Access Analyzer"
  value       = aws_accessanalyzer_analyzer.this.id
}

output "analyzer_arn" {
  description = "ARN of the IAM Access Analyzer"
  value       = aws_accessanalyzer_analyzer.this.arn
}

output "unused_access_analyzer_id" {
  description = "ID of the unused access analyzer (if created)"
  value       = var.unused_access_enabled && var.analyzer_type == "ACCOUNT" ? aws_accessanalyzer_analyzer.unused_access[0].id : null
}

output "unused_access_analyzer_arn" {
  description = "ARN of the unused access analyzer (if created)"
  value       = var.unused_access_enabled && var.analyzer_type == "ACCOUNT" ? aws_accessanalyzer_analyzer.unused_access[0].arn : null
}

output "archive_rule_ids" {
  description = "Map of rule names to their archive rule IDs"
  value       = { for name, rule in aws_accessanalyzer_archive_rule.this : name => rule.id }
}

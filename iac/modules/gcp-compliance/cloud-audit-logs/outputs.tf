output "audit_config_id" {
  description = "ID of the audit config resource"
  value = var.target_type == "project" ? (
    google_project_iam_audit_config.project[0].id
    ) : var.target_type == "folder" ? (
    google_folder_iam_audit_config.folder[0].id
    ) : (
    google_organization_iam_audit_config.organization[0].id
  )
}

output "sink_id" {
  description = "ID of the log sink"
  value = var.target_type == "project" ? (
    var.enable_log_sink ? google_logging_project_sink.project_sink[0].id : null
    ) : var.target_type == "folder" ? (
    var.enable_log_sink ? google_logging_folder_sink.folder_sink[0].id : null
    ) : (
    var.enable_log_sink ? google_logging_organization_sink.org_sink[0].id : null
  )
}

output "sink_writer_identity" {
  description = "Writer identity of the log sink"
  value = var.target_type == "project" ? (
    var.enable_log_sink ? google_logging_project_sink.project_sink[0].writer_identity : null
    ) : var.target_type == "folder" ? (
    var.enable_log_sink ? google_logging_folder_sink.folder_sink[0].writer_identity : null
    ) : (
    var.enable_log_sink ? google_logging_organization_sink.org_sink[0].writer_identity : null
  )
}

output "log_bucket_id" {
  description = "ID of the custom log bucket"
  value = var.target_type == "project" ? (
    var.enable_log_bucket ? google_logging_project_bucket_config.bucket[0].id : null
    ) : var.target_type == "folder" ? (
    var.enable_log_bucket ? google_logging_folder_bucket_config.folder_bucket[0].id : null
    ) : (
    var.enable_log_bucket ? google_logging_organization_bucket_config.org_bucket[0].id : null
  )
}

output "log_view_ids" {
  description = "IDs of the log views"
  value       = { for k, v in google_logging_log_view.view : k => v.id }
}

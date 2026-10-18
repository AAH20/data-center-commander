output "route_name" {
  description = "Name of the route"
  value       = openshift_route.this.metadata[0].name
}

output "route_namespace" {
  description = "Namespace of the route"
  value       = openshift_route.this.metadata[0].namespace
}

output "route_host" {
  description = "Host of the route"
  value       = openshift_route.this.spec[0].host
}

output "route_path" {
  description = "Path of the route"
  value       = openshift_route.this.spec[0].path
}

output "route_url" {
  description = "Full URL of the route"
  value       = "https://${openshift_route.this.spec[0].host}${openshift_route.this.spec[0].path}"
}

output "route_tls_termination" {
  description = "TLS termination type"
  value       = openshift_route.this.spec[0].tls[0].termination
}

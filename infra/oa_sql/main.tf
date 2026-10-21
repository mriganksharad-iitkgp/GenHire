terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 7.10" }
  }
}
provider "google" {
  project = var.project_id
  region  = "europe-west1"
}
variable "project_id" { type = string }
variable "billing_account" { type = string }
variable "backend_service_account" { type = string }
variable "artifact_bucket" { type = string }
variable "postgresql_image" {
  type = string
  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.postgresql_image))
    error_message = "Use a built and verified PostgreSQL image pinned by digest."
  }
}
variable "mysql_image" {
  type = string
  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.mysql_image))
    error_message = "Use a built and verified MySQL image pinned by digest."
  }
}
variable "budget_currency" {
  type    = string
  default = "USD"
}
variable "budget_units" {
  type    = string
  default = "10"
}
data "google_project" "existing" { project_id = var.project_id }
resource "google_project_service" "required" {
  for_each           = toset(["run.googleapis.com", "storage.googleapis.com", "billingbudgets.googleapis.com"])
  service            = each.value
  disable_on_destroy = false
}
resource "google_service_account" "runner" {
  account_id   = "genhire-oa-sql-runner"
  display_name = "GenHire disposable SQL validator"
}
resource "google_storage_bucket" "artifacts" {
  name                        = var.artifact_bucket
  location                    = "EUROPE-WEST1"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = { workload = "genhire-oa-sql" }
  lifecycle_rule {
    condition { age = 1 }
    action { type = "Delete" }
  }
  depends_on = [google_project_service.required]
}
resource "google_storage_bucket_iam_member" "runner_read" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runner.email}"
  condition {
    title      = "read_sql_requests"
    expression = "resource.name.startsWith('projects/_/buckets/${var.artifact_bucket}/objects/sql-validation/requests/')"
  }
}
resource "google_storage_bucket_iam_member" "runner_write" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.runner.email}"
  condition {
    title      = "write_sql_results"
    expression = "resource.name.startsWith('projects/_/buckets/${var.artifact_bucket}/objects/sql-validation/results/')"
  }
}
resource "google_storage_bucket_iam_member" "backend" {
  for_each = toset(["roles/storage.objectCreator", "roles/storage.objectViewer"])
  bucket   = google_storage_bucket.artifacts.name
  role     = each.value
  member   = "serviceAccount:${var.backend_service_account}"
}
resource "google_cloud_run_v2_job" "validator" {
  for_each            = { postgresql = { image = var.postgresql_image, version = "17" }, mysql = { image = var.mysql_image, version = "8.4" } }
  name                = "genhire-oa-sql-${each.key}"
  location            = "europe-west1"
  labels              = { workload = "genhire-oa-sql" }
  deletion_protection = true
  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account       = google_service_account.runner.email
      max_retries           = 0
      timeout               = "60s"
      execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
      containers {
        image = each.value.image
        resources { limits = { cpu = "1", memory = "1Gi" } }
        env {
          name  = "SQL_ENGINE"
          value = each.key
        }
        env {
          name  = "SQL_ENGINE_VERSION"
          value = each.value.version
        }
      }
    }
  }
  depends_on = [google_project_service.required]
}
resource "google_project_iam_custom_role" "executor" {
  role_id     = "genhireSqlJobExecutor"
  title       = "Execute configured GenHire SQL jobs"
  permissions = ["run.jobs.run", "run.jobs.runWithOverrides", "run.jobs.get", "run.executions.get"]
}
resource "google_cloud_run_v2_job_iam_member" "backend" {
  for_each = google_cloud_run_v2_job.validator
  project  = var.project_id
  location = "europe-west1"
  name     = each.value.name
  role     = google_project_iam_custom_role.executor.name
  member   = "serviceAccount:${var.backend_service_account}"
}
resource "google_billing_budget" "sql" {
  billing_account = var.billing_account
  display_name    = "GenHire OA SQL - monthly target USD 10 equivalent"
  budget_filter {
    projects        = ["projects/${data.google_project.existing.number}"]
    labels          = { workload = "genhire-oa-sql" }
    calendar_period = "MONTH"
  }
  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = var.budget_units
    }
  }
  dynamic "threshold_rules" {
    for_each = [0.5, 0.8, 1.0]
    content { threshold_percent = threshold_rules.value }
  }
  depends_on = [google_project_service.required]
}
output "sql_jobs" { value = { for key, job in google_cloud_run_v2_job.validator : key => job.name } }
output "artifact_bucket" { value = google_storage_bucket.artifacts.name }

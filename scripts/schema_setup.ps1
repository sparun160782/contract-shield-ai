param(
    [Parameter(Mandatory = $true)]
    [string]$SchemaPath
)

$ErrorActionPreference = "Stop"

$projectId = (gcloud config get-value project).Trim()
if (-not $projectId) {
    throw "No active gcloud project set."
}

if (-not (Test-Path -Path $SchemaPath)) {
    throw "Schema file not found: $SchemaPath"
}

$schema = Get-Content -Path $SchemaPath -Raw
$schema = $schema -replace "your-project-id", $projectId

$schema | bq query --use_legacy_sql=false

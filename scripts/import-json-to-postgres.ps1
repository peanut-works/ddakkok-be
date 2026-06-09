param(
    [string]$ComposeFile = "docker-compose.yml",
    [string]$ServiceName = "db",
    [string]$DatabaseName = "ddakkok",
    [string]$DatabaseUser = "ddakkok",
    [string]$ImportDirectory = ".docker/postgres-import",
    [string[]]$InputPath = @(),
    [int]$WaitSeconds = 60,
    [switch]$PrepareOnly
)

$ErrorActionPreference = "Stop"

function Resolve-WorkspacePath {
    param([string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }

    return [System.IO.Path]::GetFullPath((Join-Path -Path (Get-Location) -ChildPath $Path))
}

if ($InputPath.Count -eq 0) {
    $InputPath = @(
        "app/data/01_seed/00_seed_data.json",
        "app/data/02_mock",
        "app/data/03_scenarios"
    )
}

$composePath = Resolve-WorkspacePath -Path $ComposeFile
$importPath = Resolve-WorkspacePath -Path $ImportDirectory
$prepareScriptPath = Resolve-WorkspacePath -Path "scripts/prepare_postgres_import.py"

if (-not (Test-Path -LiteralPath $composePath)) {
    throw "Compose file not found: $composePath"
}

if (-not (Test-Path -LiteralPath $prepareScriptPath)) {
    throw "Prepare script not found: $prepareScriptPath"
}

New-Item -ItemType Directory -Force -Path $importPath | Out-Null
Get-ChildItem -LiteralPath $importPath -Filter "*.sql" -File -ErrorAction SilentlyContinue | Remove-Item -Force

$prepareArgs = @(
    "run", "python", $prepareScriptPath,
    "--database", $DatabaseName,
    "--output-dir", $ImportDirectory
)

foreach ($path in $InputPath) {
    $prepareArgs += @("--input", $path)
}

& uv @prepareArgs
if ($LASTEXITCODE -ne 0) {
    throw "Failed to prepare the PostgreSQL import SQL."
}

if ($PrepareOnly) {
    Write-Host "PrepareOnly mode enabled. Skipping Docker Compose execution."
    exit 0
}

& docker compose -f $composePath up -d $ServiceName
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start Docker Compose service '$ServiceName'."
}

$ready = $false
for ($attempt = 1; $attempt -le $WaitSeconds; $attempt++) {
    & docker compose -f $composePath exec -T $ServiceName pg_isready -U $DatabaseUser -d $DatabaseName | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $ready = $true
        break
    }

    Start-Sleep -Seconds 1
}

if (-not $ready) {
    throw "PostgreSQL did not become ready within $WaitSeconds second(s)."
}

& docker compose -f $composePath exec -T $ServiceName psql -U $DatabaseUser -d $DatabaseName -f /import/run-import.sql
if ($LASTEXITCODE -ne 0) {
    throw "Import failed while running psql in service '$ServiceName'."
}

Write-Host "PostgreSQL import completed."

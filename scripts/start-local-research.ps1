param(
    [int]$Port = 8000,
    [switch]$RequireLlm,
    [switch]$PreflightOnly
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$corpusPath = Join-Path $repoRoot "research\corpus\tcm_v1\chunks.jsonl"
$configPath = Join-Path $repoRoot "research\corpus\configs\tcm_v1.yaml"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Project Python was not found at $pythonPath. Create .venv and install backend/requirements.txt first."
}
if (-not (Test-Path -LiteralPath $corpusPath -PathType Leaf)) {
    throw "TCM Research Corpus v1 is required but missing at $corpusPath. Rebuild it from the audited local source files before starting research."
}

$env:PYTHONPATH = Join-Path $repoRoot "backend"
$env:TCM_CORPUS_MODE = "required"
$env:TCM_CORPUS_PATH = $corpusPath
$env:RESEARCH_REAL_LLM_ENABLED = if ($RequireLlm) { "true" } else { "false" }

Push-Location $repoRoot
try {
    & $pythonPath -m ingestion.validate_tcm_corpus_v1 --config $configPath | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "TCM Corpus v1 validation failed." }

    $status = & $pythonPath -c "from config import get_settings; from corpus import corpus_stats; import json; s=get_settings(); c=corpus_stats(); print(json.dumps({'corpus_name':c['corpus_name'],'corpus_version':c['corpus_version'],'chunk_count':c['chunk_count'],'source_count':c['source_count'],'corpus_mode':c['corpus_mode'],'provider_configured':s.llm_provider,'provider_ready':s.provider_mode != 'mock','llm_execution_enabled':s.research_real_llm_enabled and s.provider_mode != 'mock'}))"
    if ($LASTEXITCODE -ne 0) { throw "Local research preflight failed." }
    $parsed = $status | ConvertFrom-Json
    if ($parsed.chunk_count -ne 4461 -or $parsed.corpus_mode -ne "required") {
        throw "Expected required TCM Corpus v1 with 4,461 chunks; preflight returned $status"
    }
    if ($RequireLlm -and -not $parsed.llm_execution_enabled) {
        throw "Real LLM execution was requested, but no local LLM_API_KEY/provider is configured. Put the secret in ignored backend/.env or the process environment; never commit it."
    }

    Write-Host "Local research preflight passed: $status"
    if ($PreflightOnly) { return }
    & $pythonPath -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port $Port
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

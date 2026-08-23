param(
    [ValidateSet('status','prepare','import-benchmark','smoke','post-fix-smoke','formal','resume','dashboard','finalize','synthetic-test')]
    [string]$Action = 'status',
    [string]$Path = ''
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$pipeline = Join-Path $repo 'research\experiment_pipeline\rq4_platform.py'
if (-not (Test-Path -LiteralPath $python)) { throw "RQ4 Python environment not found: $python" }
$arguments = @($pipeline, $Action)
if ($Path) { $arguments += $Path }
& $python @arguments
exit $LASTEXITCODE

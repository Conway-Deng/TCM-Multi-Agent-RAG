param(
    [switch]$PreflightOnly,
    [switch]$DryRun,
    [switch]$SimulateResume,
    [ValidateSet('auto','prepare','preflight','run','validate','objective-evaluate','export-semantic','import-semantic','analyze','closeout')]
    [string]$Stage='auto',
    [string]$SemanticFile=''
)

$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $root '.venv\Scripts\python.exe'
$runner=Join-Path $root 'research\experiment_pipeline\rq1_confirmatory.py'
$config=Join-Path $root 'research\experiments\rq1_c1_vs_c2\confirmatory_protocol\rq1_confirmatory.yaml'
if($PreflightOnly){$Stage='preflight'}
$runnerArgs=@($runner,'--config',$config,'--stage',$Stage)
if($DryRun){$runnerArgs+='--dry-run'}
if($SimulateResume){$runnerArgs+='--simulate-resume'}
if($SemanticFile){$runnerArgs+=@('--semantic-file',$SemanticFile)}
& $python @runnerArgs
exit $LASTEXITCODE

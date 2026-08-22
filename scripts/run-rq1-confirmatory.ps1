param([switch]$PreflightOnly,[switch]$DryRun,[switch]$SimulateResume,[ValidateSet('auto','prepare','preflight','run','validate','objective-evaluate','export-semantic','import-semantic','analyze','closeout')][string]$Stage='auto',[string]$SemanticFile='')
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $root '.venv\Scripts\python.exe'
$runner=Join-Path $root 'research\experiment_pipeline\rq1_confirmatory.py'
$config=Join-Path $root 'research\experiments\rq1_c1_vs_c2\confirmatory_protocol\rq1_confirmatory.yaml'
if($PreflightOnly){$Stage='preflight'}
$args=@($runner,'--config',$config,'--stage',$Stage)
if($DryRun){$args+='--dry-run'}
if($SimulateResume){$args+='--simulate-resume'}
if($SemanticFile){$args+=@('--semantic-file',$SemanticFile)}
& $python @args
exit $LASTEXITCODE

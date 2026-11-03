$ErrorActionPreference = 'Stop'
$runtimeRoot = Join-Path (Split-Path -Parent $PSScriptRoot) '.runtime'
$pidFile = Join-Path $runtimeRoot 'server.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Output 'Não há PID de servidor iniciado por este projeto.'; exit 0 }
$recordedProcessId = [int](Get-Content -LiteralPath $pidFile -Raw)
$serverProcess = Get-Process -Id $recordedProcessId -ErrorAction SilentlyContinue
if ($serverProcess) {
    $expectedExecutable = [IO.Path]::GetFullPath((Join-Path $runtimeRoot 'ollama\ollama.exe'))
    if (-not [string]::Equals($serverProcess.Path, $expectedExecutable, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'O PID não corresponde ao runtime do projeto; nenhum processo foi encerrado.'
    }
    Stop-Process -Id $recordedProcessId
    Write-Output 'Servidor portátil do projeto encerrado.'
}

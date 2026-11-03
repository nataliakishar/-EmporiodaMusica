param([switch]$PullModel)
$ErrorActionPreference = 'Stop'
$moduleRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $moduleRoot '.runtime'
$ollamaExecutable = Join-Path $runtimeRoot 'ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $ollamaExecutable)) {
    throw 'Runtime portátil ausente. Execute prepare_ollama.py depois de concluir o download oficial.'
}
$modelsDirectory = Join-Path $runtimeRoot 'models'
New-Item -ItemType Directory -Path $modelsDirectory -Force | Out-Null
$env:OLLAMA_MODELS = $modelsDirectory
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = '4096'
$serverRunning = $false
try {
    $version = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 3
    $serverRunning = $true
} catch { }
if (-not $serverRunning) {
    $serverProcess = Start-Process -FilePath $ollamaExecutable -ArgumentList 'serve' -WorkingDirectory $runtimeRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'server.stdout.log') -RedirectStandardError (Join-Path $runtimeRoot 'server.stderr.log')
    $serverProcess.Id | Set-Content -LiteralPath (Join-Path $runtimeRoot 'server.pid')
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $version = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
            $serverRunning = $true
            break
        } catch { }
    }
}
if (-not $serverRunning) { throw 'Ollama não iniciou. Confira os logs em python-agent/.runtime/.' }
Write-Output ('Ollama acessível em localhost:11434; versão ' + $version.version)
if ($PullModel) {
    & $ollamaExecutable pull 'qwen3:1.7b'
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

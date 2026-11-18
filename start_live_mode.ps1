<# N6 live entry, separate port, advisor off. Extra arguments are passed to --help. #>
$ErrorActionPreference = "Stop"
$liveRepo = $PSScriptRoot
$livePython = if ($env:PYTHON) { $env:PYTHON } else { Join-Path $liveRepo ".venv\Scripts\python.exe" }
if (-not (Test-Path -LiteralPath $livePython -PathType Leaf)) { throw "Python environment missing: $livePython (uv sync or set PYTHON)" }
$env:PYTHONPATH = (Join-Path $liveRepo "src") + [IO.Path]::PathSeparator + $env:PYTHONPATH
$env:PYTHONDONTWRITEBYTECODE = "1"
if (-not $env:UV_CACHE_DIR) { $env:UV_CACHE_DIR = Join-Path $liveRepo ".local\demo-cache\uv" }
Push-Location $liveRepo
try {
    & uv run --offline --no-project --python $livePython python -B scripts/start_live_mode.py @args
    exit $LASTEXITCODE
} finally { Pop-Location }

param(
    [switch]$Headless,
    [int]$Steps = 240,
    [string]$Render = "",
    [switch]$Reinstall,
    [switch]$SetupOnly
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot
$VenvDir = Join-Path $ScriptDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $ScriptDir "requirements.txt"
$Stamp = Join-Path $VenvDir "stackforce-requirements.sha256"

function Write-Step([string]$Message) {
    Write-Host "[StackForce] $Message" -ForegroundColor Cyan
}

function Test-PythonCandidate([string]$Command, [string[]]$Prefix = @()) {
    if (-not (Test-Path $Command) -and -not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        return $null
    }
    try {
        & $Command @Prefix -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ Command = $Command; Prefix = $Prefix }
        }
    } catch {
        return $null
    }
    return $null
}

function Find-Python {
    $Candidates = @()
    if ($env:STACKFORCE_MUJOCO_PYTHON) {
        $Candidates += [pscustomobject]@{ Command = $env:STACKFORCE_MUJOCO_PYTHON; Prefix = @() }
    }
    $Candidates += [pscustomobject]@{ Command = "py"; Prefix = @("-3") }
    $Candidates += [pscustomobject]@{ Command = "python"; Prefix = @() }
    $Candidates += [pscustomobject]@{ Command = "python3"; Prefix = @() }

    foreach ($Candidate in $Candidates) {
        $Resolved = Test-PythonCandidate $Candidate.Command $Candidate.Prefix
        if ($Resolved) { return $Resolved }
    }

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Step "Python 3.10+ was not found. Installing Python 3.12 with winget..."
        & winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements --silent
        if ($LASTEXITCODE -ne 0) {
            throw "winget could not install Python 3.12 (exit $LASTEXITCODE)."
        }
        $InstalledCandidates = @(
            (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
            (Join-Path $env:ProgramFiles "Python312\python.exe"),
            "py",
            "python"
        )
        foreach ($Command in $InstalledCandidates) {
            $Prefix = if ($Command -eq "py") { @("-3") } else { @() }
            $Resolved = Test-PythonCandidate $Command $Prefix
            if ($Resolved) { return $Resolved }
        }
    }

    throw "Python 3.10+ is required and could not be installed automatically. Install Python from https://www.python.org/downloads/ and run this file again."
}

try {
    Write-Step "Checking the local Python and MuJoCo environment..."
    $BasePython = Find-Python

    if (-not (Test-Path $VenvPython)) {
        Write-Step "Creating an isolated environment in sim2sim\.venv..."
        $BaseCommand = [string]$BasePython.Command
        $BasePrefix = @($BasePython.Prefix)
        & $BaseCommand @BasePrefix -m venv $VenvDir
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
            throw "Could not create the Python virtual environment."
        }
    }

    $RequirementHash = (Get-FileHash -Algorithm SHA256 $Requirements).Hash.ToLowerInvariant()
    $InstalledHash = if (Test-Path $Stamp) { (Get-Content $Stamp -Raw).Trim() } else { "" }
    $ImportsReady = $false
    if (-not $Reinstall) {
        $PreviousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            & $VenvPython -c "import mujoco, numpy, onnxruntime; from PIL import Image" *> $null
            $ImportsReady = $LASTEXITCODE -eq 0
        } finally {
            $ErrorActionPreference = $PreviousErrorActionPreference
        }
    }

    if ($Reinstall -or -not $ImportsReady -or $InstalledHash -ne $RequirementHash) {
        Write-Step "Installing MuJoCo and the required Python packages. The first run needs internet access..."
        $PreviousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            & $VenvPython -m pip install --disable-pip-version-check --upgrade pip
            $PipUpgradeExitCode = $LASTEXITCODE
            if ($PipUpgradeExitCode -eq 0) {
                & $VenvPython -m pip install --disable-pip-version-check -r $Requirements
                $RequirementsExitCode = $LASTEXITCODE
            } else {
                $RequirementsExitCode = $PipUpgradeExitCode
            }
        } finally {
            $ErrorActionPreference = $PreviousErrorActionPreference
        }
        if ($PipUpgradeExitCode -ne 0) { throw "Could not update pip." }
        if ($RequirementsExitCode -ne 0) { throw "Could not install the MuJoCo requirements." }
        Set-Content -Path $Stamp -Value $RequirementHash -Encoding Ascii -NoNewline
    } else {
        Write-Step "The packaged MuJoCo environment is ready; reusing it."
    }

    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $VenvPython -c "import mujoco; print('[StackForce] MuJoCo ' + mujoco.__version__ + ' is ready.')"
        $MuJoCoImportExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
    if ($MuJoCoImportExitCode -ne 0) { throw "MuJoCo was installed but could not be imported." }
    if ($SetupOnly) { exit 0 }

    Write-Step "Starting the exported MuJoCo project..."
    $Runner = Join-Path $ScriptDir "run_mujoco.py"
    $Arguments = @($Runner, "--steps", "$Steps", "--validate-policy")
    if (-not $Headless) { $Arguments += "--viewer" }
    if ($Render) { $Arguments += @("--render", $Render) }
    $ErrorActionPreference = "Continue"
    & $VenvPython @Arguments
    exit $LASTEXITCODE
} catch {
    Write-Host "[StackForce] Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Internet access is required on the first run. You can rerun with -Reinstall after fixing the reported issue." -ForegroundColor Yellow
    exit 1
}

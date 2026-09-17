# ILANG
# [TYPE:script][PROJECT:vpsticker][LANG:zh]
# ::ROLE{Scheduled-task entry: inject persisted credentials, then call refresh.py}
# ::WHY{The task runs in a separate process and cannot inherit the app process env.
#       Credentials live in the user registry, so read them straight from there.}
# ::MUST{This file must stay pure ASCII. PowerShell 5.1 without a BOM reads
#        non-ASCII as GBK and corrupts the script. Keep every string English.}
# ::MUST{Write no file that contains the token.}
# ::BOUNDARY{never:write the token to any file|scope:permanent}
# ::BOUNDARY{never:touch the registrar, DNS records or Cloudflare settings|scope:permanent}

$ErrorActionPreference = 'Stop'

$repo = 'C:\Users\Administrator\WorkBuddy AI\2026-09-12-16-01-02\vps-deals-promo-radar'
$py   = 'C:\Users\Administrator\.workbuddy-ai\binaries\python\versions\3.13.12\python.exe'
$log  = Join-Path $repo 'task_runner.log'

function Write-Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK'), $msg
    Add-Content -Path $log -Value $line -Encoding utf8
}

try {
    if (-not (Test-Path $py)) {
        Write-Log "ABORT python not found: $py"
        exit 2
    }

    # Read credentials straight from HKCU so this does not depend on env inheritance.
    $tok = [Environment]::GetEnvironmentVariable('CLOUDFLARE_API_TOKEN', 'User')
    $acc = [Environment]::GetEnvironmentVariable('CLOUDFLARE_ACCOUNT_ID', 'User')
    if ([string]::IsNullOrWhiteSpace($tok)) {
        Write-Log 'ABORT cannot read CLOUDFLARE_API_TOKEN from the user registry'
        exit 3
    }
    if ([string]::IsNullOrWhiteSpace($acc)) {
        Write-Log 'ABORT cannot read CLOUDFLARE_ACCOUNT_ID from the user registry'
        exit 4
    }

    # Pass them on through the environment of the child process only.
    $env:CLOUDFLARE_API_TOKEN  = $tok
    $env:CLOUDFLARE_ACCOUNT_ID = $acc

    Write-Log '--- scheduled trigger ---'
    Set-Location $repo

    $out  = & $py 'refresh.py' 2>&1
    $code = $LASTEXITCODE
    foreach ($l in $out) { Write-Log ('refresh| ' + $l.ToString()) }
    Write-Log "refresh.py exit=$code"
    exit $code
}
catch {
    Write-Log ('EXCEPTION ' + $_.Exception.Message)
    exit 5
}

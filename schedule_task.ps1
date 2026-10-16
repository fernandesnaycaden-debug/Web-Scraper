# Registers a daily Windows Task Scheduler job that runs the scraper and emails the report.
# Usage:  powershell -ExecutionPolicy Bypass -File .\schedule_task.ps1 [-Time "08:00"]
# Remove: Unregister-ScheduledTask -TaskName "BookPriceScraper" -Confirm:$false
param(
    [string]$Time = "08:00",
    [string]$TaskName = "BookPriceScraper"
)

$ProjectDir = $PSScriptRoot
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Virtual env not found at $Python. Create it first: python -m venv .venv"
    exit 1
}

$Action  = New-ScheduledTaskAction -Execute $Python -Argument "main.py --email" -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
# StartWhenAvailable: run it later if the PC was off at the scheduled time.
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "Daily books.toscrape.com price scrape + email report" -Force | Out-Null

Write-Host "Registered '$TaskName' to run daily at $Time."
Write-Host "Test it now with: Start-ScheduledTask -TaskName $TaskName"

param([ValidateSet('start','stop','setup','remove')][string]$Action='start')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$python=Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$entry=Join-Path $projectRoot 'Dashboard.vbs'
$shell=New-Object -ComObject WScript.Shell
$desktopLink=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Job Apply Dashboard.lnk'
$menuFolder=Join-Path ([Environment]::GetFolderPath('Programs')) 'Job Apply Dashboard'
$registry='HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\JobApplyDashboard'
function Shortcut($Path,$Argument) {
    $link=$shell.CreateShortcut($Path)
    $link.TargetPath=Join-Path $env:WINDIR 'System32\wscript.exe'
    $link.Arguments='"'+$entry+'" '+$Argument
    $link.WorkingDirectory=$projectRoot
    $link.IconLocation=Join-Path $projectRoot 'scripts\assets\dashboard.ico'
    $link.Save()
}
try {
    Set-Location -LiteralPath $projectRoot
    if($Action -eq 'setup') {
        New-Item -ItemType Directory -Path $menuFolder -Force | Out-Null
        Shortcut $desktopLink 'start'
        Shortcut (Join-Path $menuFolder 'Open Dashboard.lnk') 'start'
        Shortcut (Join-Path $menuFolder 'Stop Dashboard.lnk') 'stop'
        Shortcut (Join-Path $menuFolder 'Remove Dashboard.lnk') 'remove'
        New-Item -Path $registry -Force | Out-Null
        New-ItemProperty -Path $registry -Name DisplayName -Value 'Job Apply Dashboard' -Force | Out-Null
        New-ItemProperty -Path $registry -Name UninstallString -Value ('wscript.exe "'+$entry+'" remove') -Force | Out-Null
        New-ItemProperty -Path $registry -Name InstallLocation -Value $projectRoot -Force | Out-Null
        New-ItemProperty -Path $registry -Name DisplayIcon -Value (Join-Path $projectRoot 'scripts\assets\dashboard.ico') -Force | Out-Null
    } elseif($Action -eq 'remove') {
        if(Test-Path -LiteralPath $python) { & $python -m app.dashboard_entry stop; if($LASTEXITCODE) { throw 'Stop the previous backend before removing Dashboard shortcuts.' } }
        # Remove only the exact shortcuts we created, never any candidate data.
        foreach($path in @($desktopLink,(Join-Path $menuFolder 'Open Dashboard.lnk'),(Join-Path $menuFolder 'Stop Dashboard.lnk'),(Join-Path $menuFolder 'Remove Dashboard.lnk'))) {
            if(Test-Path -LiteralPath $path) {
                $link=$shell.CreateShortcut($path)
                if($link.Arguments.StartsWith('"'+$entry+'" ')) { Remove-Item -LiteralPath $path }
            }
        }
        if((Test-Path -LiteralPath $menuFolder) -and !(Get-ChildItem -LiteralPath $menuFolder)) { Remove-Item -LiteralPath $menuFolder }
        if(Test-Path $registry) { Remove-Item -LiteralPath $registry }
    } else {
        if(!(Test-Path -LiteralPath $python)) { throw 'Run run_windows.bat once to prepare Python, then open Dashboard again.' }
        & $python -m app.dashboard_entry $Action
        if($LASTEXITCODE) { exit $LASTEXITCODE }
    }
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'Job Apply Dashboard') | Out-Null
    exit 1
}

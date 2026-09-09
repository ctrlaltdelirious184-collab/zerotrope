$vbsPath = "c:\Users\Evan\Desktop\AI-Marketing-Pipeline\run_discord_bot.vbs"
$desktopPath = [System.IO.Path]::Combine([Environment]::GetFolderPath("Desktop"), "Run Discord Bot.lnk")

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($desktopPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$vbsPath`""
$Shortcut.WorkingDirectory = "c:\Users\Evan\Desktop\AI-Marketing-Pipeline"
$Shortcut.IconLocation = "shell32.dll,14"
$Shortcut.Description = "Start AI Marketing Discord Bot"
$Shortcut.Save()

Write-Host "Desktop shortcut created at: $desktopPath"

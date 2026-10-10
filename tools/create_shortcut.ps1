param([string]$AppDir)
$AppDir = $AppDir.TrimEnd('\')
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\SmartScreen Helio.lnk')
$lnk.TargetPath = "$AppDir\.venv\Scripts\pythonw.exe"
$lnk.Arguments = '"' + "$AppDir\app.py" + '"'
$lnk.WorkingDirectory = $AppDir
$lnk.IconLocation = "$AppDir\res\icons\app.ico"
$lnk.Save()

Option Explicit
Dim shell, fs, root, action, command
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
action = "start"
If WScript.Arguments.Count > 0 Then action = LCase(WScript.Arguments(0))
Select Case action
  Case "start", "stop", "setup", "remove"
  Case Else
    WScript.Quit 1
End Select
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & Chr(34) & root & "\scripts\dashboard.ps1" & Chr(34) & " -Action " & action
shell.Run command, 0, False

' AI Teleprompter - Silent Launcher
' Completely silent execution with 0 console or CMD windows

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDirectory = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDirectory

electronExe = strDirectory & "\node_modules\electron\dist\electron.exe"

If fso.FileExists(electronExe) Then
    WshShell.Run """" & electronExe & """ """ & strDirectory & """", 0, False
Else
    WshShell.Run "cmd.exe /c start.bat", 0, False
End If

Set WshShell = Nothing
Set fso = Nothing

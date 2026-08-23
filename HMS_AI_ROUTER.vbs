Option Explicit
Dim shell, fso, base, gui, q, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
q = Chr(34)
gui = base & "\_runtime\HMS_GUI.pyw"

On Error Resume Next

Err.Clear
cmd = "pyw.exe -3 " & q & gui & q
shell.Run cmd, 0, False
If Err.Number = 0 Then WScript.Quit 0

Err.Clear
cmd = "pythonw.exe " & q & gui & q
shell.Run cmd, 0, False
If Err.Number = 0 Then WScript.Quit 0

Err.Clear
shell.Run q & gui & q, 1, False
If Err.Number = 0 Then WScript.Quit 0

MsgBox "HMS GUI could not start." & vbCrLf & _
       "Python GUI launcher was not found." & vbCrLf & _
       "Install/repair Python Launcher or Python, then try again." & vbCrLf & _
       "Error: " & Err.Description, vbCritical, "HMS-AI-ROUTER"

Option Explicit
Dim shell, fso, base, gui, reviewGui, safeGui, legacyGui, q, cmd
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
q = Chr(34)
gui = base & "\_runtime\HMS_GUI_RECOVERY_ENTRY.pyw"
reviewGui = base & "\_runtime\HMS_GUI_REVIEW_ENTRY.pyw"
safeGui = base & "\_runtime\HMS_GUI_SAFE_FALLBACK.pyw"
legacyGui = base & "\_runtime\HMS_GUI.pyw"

' v25.75 fail-closed path:
' recovery UX wrapper -> sealed reviewer wrapper -> promotion-disabled safe fallback -> legacy core.
' Missing recovery UX may fall back to the sealed reviewer wrapper.
' Never fall directly to HMS_GUI_ENTRY.pyw because that extension can render Promotion Review without the principal sealed-loader wrapper.
If Not fso.FileExists(gui) Then gui = reviewGui
If Not fso.FileExists(gui) Then gui = safeGui
If Not fso.FileExists(gui) Then gui = legacyGui

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

# Builds dist\NousPDF\NousPDF.exe. Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File C:\Users\wrong\NousPDF\build.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"

& $py -m pip install --quiet -r (Join-Path $root "requirements.txt")
& $py (Join-Path $root "make_icon.py")
& $py -m PyInstaller --noconfirm --clean --windowed --name NousPDF `
    --icon (Join-Path $root "icon.ico") `
    --version-file (Join-Path $root "version_info.txt") `
    --add-data "$(Join-Path $root 'icon.ico');." `
    --distpath (Join-Path $root "dist") --workpath (Join-Path $root "build") `
    --specpath (Join-Path $root "build") `
    --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml `
    --exclude-module PySide6.QtQuick --exclude-module PySide6.QtPdf `
    (Join-Path $root "nouspdf.py")

# Qt drags in pieces this app never uses (QML, software OpenGL, Qt's own PDF
# module, TLS, the on-screen keyboard, translations). Drop them.
$qt = Join-Path $root "dist\NousPDF\_internal\PySide6"
$drop = @("opengl32sw.dll", "Qt6Quick*.dll", "Qt6Qml*.dll", "Qt6Pdf*.dll", "Qt6Network.dll",
          "QtNetwork.pyd", "Qt6VirtualKeyboard*.dll", "Qt6OpenGL*.dll", "translations",
          "plugins\tls", "plugins\platforminputcontexts", "plugins\networkinformation",
          "plugins\imageformats\qpdf.dll", "plugins\imageformats\qsvg.dll",
          "plugins\iconengines", "Qt6Svg.dll")
foreach ($d in $drop) { Remove-Item (Join-Path $qt $d) -Recurse -Force -ErrorAction SilentlyContinue }
$mb = (Get-ChildItem (Join-Path $root "dist\NousPDF") -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("Size: {0:N0} MB" -f $mb)
Write-Host "Built: $(Join-Path $root 'dist\NousPDF\NousPDF.exe')"

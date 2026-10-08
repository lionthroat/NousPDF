; Inno Setup script for NousPDF-Setup.exe (https://jrsoftware.org/isinfo.php).
; build.ps1 runs it after building dist\NousPDF; GitHub does the same on version tags.
;
; Installs for the current user only (no admin prompt) into
; %LOCALAPPDATA%\Programs\Nous PDF, with a Start menu entry, an optional desktop
; shortcut, an uninstaller in Settings > Apps, and a listing in "Open with" and
; Settings > Default apps for PDFs. Windows doesn't let installers make
; themselves the default; the user picks it once.

#define AppName "Nous PDF"
#define AppExe "NousPDF.exe"
#define AppVersion Trim(FileRead(FileOpen(AddBackslash(SourcePath) + "VERSION")))
#define ProgId "NousPDF.Document"

[Setup]
; Never change AppId: it's how a newer installer finds and replaces an older install.
AppId={{08B03CFC-CD71-4DCB-BB75-54305EA5093E}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=lionthroat
AppPublisherURL=https://nouspdf.lionthroat.com
AppSupportURL=https://github.com/lionthroat/NousPDF
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
CloseApplications=yes
OutputDir=installer-output
OutputBaseFilename=NousPDF-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} Setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Put a {#AppName} shortcut on the desktop"; GroupDescription: "Shortcuts:"

[Files]
Source: "dist\NousPDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; An update replaces the whole program folder, so files a newer build dropped don't linger
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; HKA = the current user's registry hive here, since the install is per-user.
; A "PDF document, opened by Nous PDF" file type
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueData: "PDF Document"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExe},0"
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""
; ...offered for .pdf files in "Open with"
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""
; ...and listed in Settings > Apps > Default apps
Root: HKA; Subkey: "Software\{#AppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\{#AppName}\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#AppName}"
Root: HKA; Subkey: "Software\{#AppName}\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "A lightweight PDF viewer with a page panel."
Root: HKA; Subkey: "Software\{#AppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "{#ProgId}"
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#AppName}"; ValueData: "Software\{#AppName}\Capabilities"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "Open {#AppName} now"; Flags: nowait postinstall skipifsilent

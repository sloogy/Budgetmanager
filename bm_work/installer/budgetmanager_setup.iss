; BudgetManager Windows Installer Script
; Für Inno Setup (https://jrsoftware.org/isinfo.php)
; 
; Verwendung:
; 1. PyInstaller ausführen um EXE zu erstellen:
;    pyinstaller --onefile --windowed --icon=icon.ico --name=BudgetManager main.py
; 2. Inno Setup Compiler auf dieses Skript ausführen
;
; Voraussetzungen:
; - Inno Setup 6.x installiert
; - PyInstaller EXE im dist/ Ordner

#define MyAppName "BudgetManager"
#define MyAppVersion "0.17.0"
#define MyAppPublisher "BudgetManager Team"
#define MyAppURL "https://github.com/yourusername/budgetmanager"
#define MyAppExeName "BudgetManager.exe"

[Setup]
AppId={{8F9A3B2C-D4E6-4A1B-9C7E-5F2D3A8B1C6D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE.txt
OutputDir=installer_output
OutputBaseFilename=BudgetManager_Setup_{#MyAppVersion}
SetupIconFile=icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "budgetmanager_settings.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\BudgetManager"
Type: filesandordirs; Name: "{localappdata}\BudgetManager"

[Code]
var
  DataDirPage: TInputDirWizardPage;

procedure InitializeWizard;
begin
  // Seite für Datenverzeichnis hinzufügen
  DataDirPage := CreateInputDirPage(wpSelectDir,
    'Datenverzeichnis auswählen', 
    'Wo sollen Ihre BudgetManager-Daten gespeichert werden?',
    'Wählen Sie den Ordner, in dem Ihre Datenbank und Backups gespeichert werden sollen, und klicken Sie dann auf Weiter.' + #13#10#13#10 +
    'Hinweis: Dieses Verzeichnis wird NICHT bei der Deinstallation gelöscht.',
    False, '');
  DataDirPage.Add('');
  DataDirPage.Values[0] := ExpandConstant('{userdocs}\BudgetManager');
end;

function GetDataDir(Param: String): String;
begin
  Result := DataDirPage.Values[0];
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  SettingsFile: String;
  SettingsContent: TArrayOfString;
  I: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Einstellungsdatei mit Datenverzeichnis erstellen/aktualisieren
    SettingsFile := ExpandConstant('{app}\budgetmanager_settings.json');
    
    // Wenn Datei nicht existiert, Standard-Einstellungen schreiben
    if not FileExists(SettingsFile) then
    begin
      SaveStringToFile(SettingsFile, 
        '{' + #13#10 +
        '  "data_directory": "' + DataDirPage.Values[0] + '",' + #13#10 +
        '  "backup_directory": "' + DataDirPage.Values[0] + '\Backups",' + #13#10 +
        '  "theme": "modern",' + #13#10 +
        '  "language": "de"' + #13#10 +
        '}', False);
    end;
  end;
end;

[CustomMessages]
german.CreateDesktopIcon=Symbol auf dem Desktop erstellen
german.CreateQuickLaunchIcon=Symbol in der Schnellstartleiste erstellen
german.LaunchProgram=%1 starten
german.UninstallProgram=%1 deinstallieren
english.CreateDesktopIcon=Create a desktop icon
english.CreateQuickLaunchIcon=Create a Quick Launch icon
english.LaunchProgram=Launch %1
english.UninstallProgram=Uninstall %1

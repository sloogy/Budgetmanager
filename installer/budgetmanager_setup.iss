; BudgetManager Windows Installer Script
; Für Inno Setup (https://jrsoftware.org/isinfo.php)
; 
; Verwendung:
; 1. PyInstaller ausführen um EXE zu erstellen:
;    pyinstaller BudgetManager.spec --noconfirm
; 2. Inno Setup Compiler auf dieses Skript ausführen
;
; Voraussetzungen:
; - Inno Setup 6.x installiert
; - PyInstaller onedir-Build im dist\BudgetManager\ Ordner

#define MyAppName "BudgetManager"
#define MyAppVersion "2.2.73"
#define MyAppPublisher "Christian"
#define MyAppURL "https://github.com/sloogy/Budgetmanager"
#define MyAppExeName "BudgetManager.exe"

[Setup]
SourceDir=..
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
SetupIconFile=resources\icons\budgetmanager.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Hauptprogramm
Source: "dist\BudgetManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Dokumentation
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "docs\USER_GUIDE*.md"; DestDir: "{app}\docs"; Flags: ignoreversion

; Sprachdateien (PFLICHT - ohne diese startet die App nicht)
Source: "locales\*"; DestDir: "{app}\locales"; Flags: ignoreversion recursesubdirs createallsubdirs

; Statische Standard-Kategorien (keine Nutzerdaten).
; Nutzer-DB, users.json, Backups, Exporte, Updates und Settings liegen im gewählten Datenordner.
Source: "data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist

; Theme-Profile (PFLICHT - ohne diese kein Theme-System)
Source: "views\profiles\*"; DestDir: "{app}\views\profiles"; Flags: ignoreversion recursesubdirs createallsubdirs

; App-Icon und Icon-Varianten
Source: "resources\icons\*"; DestDir: "{app}\resources\icons"; Flags: ignoreversion recursesubdirs createallsubdirs

; Hinweis: budgetmanager_settings.json wird NICHT mehr aus [Files] kopiert.
; Sie wird im [Code]-Abschnitt korrekt nach {app}\data\ geschrieben
; (die App liest die Settings aus dem data-Ordner).

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Der Installationsmarker gehört zum Programm, nicht zu den Nutzerdaten.
Type: files; Name: "{app}\installation.json"
; Bewusst kein Löschen des gewählten Datenordners: Nutzerdaten bleiben erhalten.

[Code]
var
  DataDirPage: TInputDirWizardPage;
  PrefsPage: TWizardPage;
  CbLanguage: TNewComboBox;
  CbCurrency: TNewComboBox;
  CbDay: TNewComboBox;
  PreviousDataDir: String;

{ Backslashes und Anführungszeichen für gültiges JSON escapen. }
function JsonEscape(const S: String): String;
begin
  Result := S;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

{ Beschriftung über einem Eingabefeld erzeugen. }
procedure AddLabel(APage: TWizardPage; const ACaption: String; ATop: Integer);
var
  L: TNewStaticText;
begin
  L := TNewStaticText.Create(APage);
  L.Parent := APage.Surface;
  L.Top := ATop;
  L.Left := 0;
  L.AutoSize := True;
  L.Caption := ACaption;
end;

function InstallerUpdateMode: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE_MODE|0}') = '1';
end;

function ExtractJsonStringValue(const Json, Key: String): String;
var
  Pattern: String;
  StartPos: Integer;
  ValueStart: Integer;
  ValueEnd: Integer;
  Rest: String;
begin
  Result := '';
  Pattern := '"' + Key + '":';
  StartPos := Pos(Pattern, Json);
  if StartPos = 0 then
    Exit;

  Rest := Copy(Json, StartPos + Length(Pattern), Length(Json));
  ValueStart := Pos('"', Rest);
  if ValueStart = 0 then
    Exit;

  Delete(Rest, 1, ValueStart);
  ValueEnd := Pos('"', Rest);
  if ValueEnd = 0 then
    Exit;

  Result := Copy(Rest, 1, ValueEnd - 1);
  StringChangeEx(Result, '\\', '\', True);
  StringChangeEx(Result, '\"', '"', True);
end;

function ExistingDataDirFromMarker: String;
var
  MarkerFile: String;
  AppDir: String;
  JsonText: AnsiString;
begin
  Result := '';

  { In InitializeWizard ist die App-Pfad-Konstante noch nicht initialisiert.
    WizardDirValue enthält hier den aktuellen/Default-Installationspfad. }
  AppDir := WizardDirValue;
  if AppDir = '' then
    AppDir := ExpandConstant('{autopf}\{#MyAppName}');

  MarkerFile := AddBackslash(AppDir) + 'installation.json';
  if FileExists(MarkerFile) then
  begin
    if LoadStringFromFile(MarkerFile, JsonText) then
      Result := ExtractJsonStringValue(JsonText, 'data_directory');
  end;
end;

function InitialDataDir: String;
var
  ParamDataDir: String;
begin
  ParamDataDir := ExpandConstant('{param:DATA_DIR|}');
  if ParamDataDir <> '' then
    Result := ParamDataDir
  else if PreviousDataDir <> '' then
    Result := PreviousDataDir
  else
    Result := ExpandConstant('{userdocs}\BudgetManager');
end;

procedure InitializeWizard;
var
  y: Integer;
  i: Integer;
begin
  PreviousDataDir := ExistingDataDirFromMarker;

  { --- Seite 1: Datenverzeichnis (bestehend) --- }
  DataDirPage := CreateInputDirPage(wpSelectDir,
    CustomMessage('DataDirTitle'),
    CustomMessage('DataDirSubtitle'),
    CustomMessage('DataDirDescription') + #13#10#13#10 +
    CustomMessage('DataDirUninstallNote'),
    False, '');
  DataDirPage.Add('');
  DataDirPage.Values[0] := InitialDataDir;

  { --- Seite 2: BudgetManager-Grundeinstellungen --- }
  PrefsPage := CreateCustomPage(DataDirPage.ID,
    CustomMessage('PrefsTitle'),
    CustomMessage('PrefsSubtitle'));

  y := ScaleY(4);

  { Sprache }
  AddLabel(PrefsPage, CustomMessage('LanguageLabel'), y);
  CbLanguage := TNewComboBox.Create(PrefsPage);
  CbLanguage.Parent := PrefsPage.Surface;
  CbLanguage.Style := csDropDownList;
  CbLanguage.Top := y + ScaleY(16);
  CbLanguage.Left := 0;
  CbLanguage.Width := PrefsPage.SurfaceWidth;
  CbLanguage.Items.Add('Deutsch');
  CbLanguage.Items.Add('English');
  CbLanguage.Items.Add('Français');
  { Vorauswahl anhand der Installer-Sprache }
  if ActiveLanguage = 'english' then
    CbLanguage.ItemIndex := 1
  else if ActiveLanguage = 'french' then
    CbLanguage.ItemIndex := 2
  else
    CbLanguage.ItemIndex := 0;

  y := y + ScaleY(52);

  { Währung }
  AddLabel(PrefsPage, CustomMessage('CurrencyLabel'), y);
  CbCurrency := TNewComboBox.Create(PrefsPage);
  CbCurrency.Parent := PrefsPage.Surface;
  CbCurrency.Style := csDropDownList;
  CbCurrency.Top := y + ScaleY(16);
  CbCurrency.Left := 0;
  CbCurrency.Width := PrefsPage.SurfaceWidth;
  CbCurrency.Items.Add(CustomMessage('CurrencyCHF'));
  CbCurrency.Items.Add(CustomMessage('CurrencyEUR'));
  CbCurrency.Items.Add(CustomMessage('CurrencyUSD'));
  CbCurrency.Items.Add(CustomMessage('CurrencyGBP'));
  CbCurrency.ItemIndex := 0;

  y := y + ScaleY(52);

  { Bevorzugter Buchungstag (für wiederkehrende Buchungen) }
  AddLabel(PrefsPage, CustomMessage('PreferredDayLabel'), y);
  CbDay := TNewComboBox.Create(PrefsPage);
  CbDay.Parent := PrefsPage.Surface;
  CbDay.Style := csDropDownList;
  CbDay.Top := y + ScaleY(16);
  CbDay.Left := 0;
  CbDay.Width := PrefsPage.SurfaceWidth;
  CbDay.Items.Add(CustomMessage('PreferredDayNone'));
  for i := 1 to 28 do
    CbDay.Items.Add(IntToStr(i));
  CbDay.Items.Add(CustomMessage('PreferredDayEndOfMonth'));
  { Index 25 entspricht Tag 25 (Index 0 = Keiner, Index 1 = Tag 1, ...) }
  CbDay.ItemIndex := 25;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if InstallerUpdateMode then
  begin
    if (PageID = DataDirPage.ID) or (PageID = PrefsPage.ID) then
      Result := True;
  end;
end;

function GetDataDir(Param: String): String;
begin
  Result := DataDirPage.Values[0];
end;

{ Auswahl -> App-Sprachcode (de/en/fr) }
function SelectedLanguageCode: String;
begin
  case CbLanguage.ItemIndex of
    1: Result := 'en';
    2: Result := 'fr';
  else
    Result := 'de';
  end;
end;

{ Auswahl -> Währungscode (CHF/EUR/USD/GBP) }
function SelectedCurrencyCode: String;
begin
  case CbCurrency.ItemIndex of
    1: Result := 'EUR';
    2: Result := 'USD';
    3: Result := 'GBP';
  else
    Result := 'CHF';
  end;
end;

{ Auswahl -> bevorzugter Tag: 0 = Keiner, 1..28, 31 = Monatsende }
function SelectedPreferredDay: Integer;
begin
  if CbDay.ItemIndex = 0 then
    Result := 0                                  { Keiner }
  else if CbDay.ItemIndex = CbDay.Items.Count - 1 then
    Result := 31                                 { Monatsende }
  else
    Result := CbDay.ItemIndex;                   { Index entspricht Tag 1..28 }
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  DataDir: String;
  SettingsFile: String;
  Json: String;
begin
  if CurStep = ssPostInstall then
  begin
    DataDir := DataDirPage.Values[0];
    if DataDir = '' then
      DataDir := InitialDataDir;

    { Installationsart-Marker: kleiner Bootstrap im Programmordner.
      Alle veränderlichen Daten liegen im gewählten Datenordner. }
    SaveStringToFile(ExpandConstant('{app}\installation.json'),
      '{' + #13#10 +
      '  "install_type": "windows_installer",' + #13#10 +
      '  "version": "{#MyAppVersion}",' + #13#10 +
      '  "app_directory": "' + JsonEscape(ExpandConstant('{app}')) + '",' + #13#10 +
      '  "data_directory": "' + JsonEscape(DataDir) + '"' + #13#10 +
      '}', False);

    { Die App liest ihre Einstellungen bei Installer-Installationen aus dem
      gewählten Datenordner, nicht aus dem Programmordner-data. }
    ForceDirectories(DataDir);
    ForceDirectories(DataDir + '\backups');
    ForceDirectories(DataDir + '\exports');
    ForceDirectories(DataDir + '\updates');
    SettingsFile := DataDir + '\budgetmanager_settings.json';

    { Nur beim Erst-Setup schreiben – bestehende Nutzereinstellungen nicht überschreiben. }
    if not FileExists(SettingsFile) then
    begin
      Json :=
        '{' + #13#10 +
        '  "language": "' + SelectedLanguageCode + '",' + #13#10 +
        '  "language_selected": true,' + #13#10 +
        '  "currency": "' + SelectedCurrencyCode + '",' + #13#10 +
        '  "recurring_preferred_day": ' + IntToStr(SelectedPreferredDay) + ',' + #13#10 +
        '  "theme": "modern",' + #13#10 +
        '  "data_directory": "' + JsonEscape(DataDir) + '",' + #13#10 +
        '  "backup_directory": "' + JsonEscape(DataDir + '\backups') + '"' + #13#10 +
        '}';
      SaveStringToFile(SettingsFile, Json, False);
    end;
  end;
end;

[CustomMessages]
german.CreateDesktopIcon=Symbol auf dem Desktop erstellen
german.CreateQuickLaunchIcon=Symbol in der Schnellstartleiste erstellen
german.LaunchProgram=%1 starten
german.UninstallProgram=%1 deinstallieren
german.DataDirTitle=Datenverzeichnis auswählen
german.DataDirSubtitle=Wo sollen Ihre BudgetManager-Daten gespeichert werden?
german.DataDirDescription=Wählen Sie den Ordner, in dem Ihre Datenbank und Backups gespeichert werden sollen, und klicken Sie dann auf Weiter.
german.DataDirUninstallNote=Hinweis: Dieses Verzeichnis wird NICHT bei der Deinstallation gelöscht.
german.PrefsTitle=BudgetManager-Einstellungen
german.PrefsSubtitle=Sprache, Währung und bevorzugter Buchungstag. Diese Werte werden beim ersten Start übernommen und können später jederzeit in den Einstellungen geändert werden.
german.LanguageLabel=Sprache:
german.CurrencyLabel=Währung:
german.CurrencyCHF=CHF – Schweizer Franken
german.CurrencyEUR=EUR – Euro
german.CurrencyUSD=USD – US-Dollar
german.CurrencyGBP=GBP – Britisches Pfund
german.PreferredDayLabel=Bevorzugter Tag für wiederkehrende Buchungen:
german.PreferredDayNone=Keiner (manuell festlegen)
german.PreferredDayEndOfMonth=Monatsende
english.CreateDesktopIcon=Create a desktop icon
english.CreateQuickLaunchIcon=Create a Quick Launch icon
english.LaunchProgram=Launch %1
english.UninstallProgram=Uninstall %1
english.DataDirTitle=Select data folder
english.DataDirSubtitle=Where should BudgetManager store your data?
english.DataDirDescription=Choose the folder where your database and backups should be stored, then click Next.
english.DataDirUninstallNote=Note: This folder will NOT be deleted when uninstalling.
english.PrefsTitle=BudgetManager settings
english.PrefsSubtitle=Language, currency and preferred booking day. These values are used on first start and can be changed later in Settings.
english.LanguageLabel=Language:
english.CurrencyLabel=Currency:
english.CurrencyCHF=CHF – Swiss franc
english.CurrencyEUR=EUR – Euro
english.CurrencyUSD=USD – US dollar
english.CurrencyGBP=GBP – British pound
english.PreferredDayLabel=Preferred day for recurring bookings:
english.PreferredDayNone=None (set manually)
english.PreferredDayEndOfMonth=End of month
french.CreateDesktopIcon=Créer une icône sur le bureau
french.CreateQuickLaunchIcon=Créer une icône dans la barre de lancement rapide
french.LaunchProgram=Lancer %1
french.UninstallProgram=Désinstaller %1
french.DataDirTitle=Choisir le dossier de données
french.DataDirSubtitle=Où BudgetManager doit-il enregistrer vos données ?
french.DataDirDescription=Choisissez le dossier dans lequel la base de données et les sauvegardes seront stockées, puis cliquez sur Suivant.
french.DataDirUninstallNote=Remarque : ce dossier ne sera PAS supprimé lors de la désinstallation.
french.PrefsTitle=Paramètres de BudgetManager
french.PrefsSubtitle=Langue, devise et jour de saisie préféré. Ces valeurs sont appliquées au premier démarrage et peuvent être modifiées plus tard dans les paramètres.
french.LanguageLabel=Langue :
french.CurrencyLabel=Devise :
french.CurrencyCHF=CHF – franc suisse
french.CurrencyEUR=EUR – euro
french.CurrencyUSD=USD – dollar américain
french.CurrencyGBP=GBP – livre sterling
french.PreferredDayLabel=Jour préféré pour les écritures récurrentes :
french.PreferredDayNone=Aucun (définir manuellement)
french.PreferredDayEndOfMonth=Fin du mois

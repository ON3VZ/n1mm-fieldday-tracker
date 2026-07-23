; Inno Setup script for N1MM Field Day Tracker
; Build with: iscc packaging\installer.iss   (after PyInstaller has produced dist\)
; Requires admin (firewall rule + Program Files) — see PrivilegesRequired.

#define AppName "N1MM Field Day Tracker"
#define AppExe "N1MMFieldDayTracker.exe"
#define AppPublisher "WLD / ON6WL"
; AppVersion is passed in from build.bat via /DAppVersion=..., with a fallback:
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\N1MMFieldDayTracker
DefaultGroupName=N1MM Field Day Tracker
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=N1MMFieldDayTracker-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Admin needed for Program Files + the Windows Firewall rule.
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; The whole PyInstaller one-folder output:
Source: "..\dist\N1MMFieldDayTracker\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; A copy of the manual next to the program:
Source: "..\docs\HANDLEIDING.md"; DestDir: "{app}\docs"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\docs\N1MM_Field_Day_Tracker_Documentatie.pdf"; DestDir: "{app}\docs"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\N1MM Field Day Tracker"; Filename: "{app}\{#AppExe}"
Name: "{group}\Handleiding (PDF)"; Filename: "{app}\docs\N1MM_Field_Day_Tracker_Documentatie.pdf"; Flags: createonlyiffileexists
Name: "{group}\{cm:UninstallProgram,N1MM Field Day Tracker}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\N1MM Field Day Tracker"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; Launch after install if the user wants to.
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,N1MM Field Day Tracker}"; Flags: nowait postinstall skipifsilent

; --- Firewall rule so N1MM UDP can reach the tracker (added on install) ---
[Code]
var
  DefaultsPage: TInputQueryWizardPage;
  FinishReminderShown: Boolean;

procedure InitializeWizard;
begin
  { A custom page asking whether to set default values, and letting the user
    change UDP host/port and language before first run. }
  DefaultsPage := CreateInputQueryPage(wpSelectTasks,
    'Standaardinstellingen',
    'Wil je de standaardwaarden gebruiken?',
    'Deze waarden werken voor de meeste opstellingen (N1MM op dezelfde laptop).'
    + #13#10 + 'Je kan ze later altijd wijzigen in de app onder Beheer > Instellingen.');
  DefaultsPage.Add('UDP-luisteradres (127.0.0.1 = deze laptop):', False);
  DefaultsPage.Add('UDP-poort (moet gelijk zijn aan N1MM):', False);
  DefaultsPage.Add('Taal (nl / en / fr):', False);
  DefaultsPage.Values[0] := '127.0.0.1';
  DefaultsPage.Values[1] := '12060';
  DefaultsPage.Values[2] := 'nl';
end;

function GetSettingsJson(): String;
begin
  { Build a minimal app_settings.json written to the user's data folder. }
  Result :=
    '{' + #13#10 +
    '  "ui_language": "' + DefaultsPage.Values[2] + '",' + #13#10 +
    '  "n1mm_udp_host": "' + DefaultsPage.Values[0] + '",' + #13#10 +
    '  "n1mm_udp_port": ' + DefaultsPage.Values[1] + #13#10 +
    '}';
end;

procedure WriteDefaultSettings();
var
  DataDir: String;
  SettingsPath: String;
begin
  { %LOCALAPPDATA%\N1MM Field Day Tracker\app_settings.json — only written
    if it does not exist yet, so we never overwrite a returning user's config. }
  DataDir := ExpandConstant('{localappdata}\N1MM Field Day Tracker');
  if not DirExists(DataDir) then
    ForceDirectories(DataDir);
  SettingsPath := DataDir + '\app_settings.json';
  if not FileExists(SettingsPath) then
    SaveStringToFile(SettingsPath, GetSettingsJson(), False);
end;

procedure AddFirewallRule();
var
  ResultCode: Integer;
begin
  { Allow the program through the Windows Firewall for UDP reception.
    Remove any old rule first so re-installs stay clean. }
  Exec('netsh', 'advfirewall firewall delete rule name="N1MM Field Day Tracker"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('netsh',
    'advfirewall firewall add rule name="N1MM Field Day Tracker" dir=in action=allow'
    + ' program="' + ExpandConstant('{app}\{#AppExe}') + '" enable=yes profile=any',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    WriteDefaultSettings();
    AddFirewallRule();
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  { On the final page, remind the user to configure N1MM. }
  if (CurPageID = wpFinished) and (not FinishReminderShown) then
  begin
    FinishReminderShown := True;
    MsgBox(
      'Vergeet niet N1MM in te stellen!' + #13#10 + #13#10 +
      'In N1MM Logger+:' + #13#10 +
      '1. Config > Configure Ports, Mode Control, Audio, Other...' + #13#10 +
      '2. Tabblad "Broadcast Data"' + #13#10 +
      '3. Vink "Contacts" aan (niet Lookup)' + #13#10 +
      '4. Bestemming: ' + DefaultsPage.Values[0] + ':' + DefaultsPage.Values[1] + #13#10 +
      '5. Contest: FDREG1' + #13#10 + #13#10 +
      'Log een test-QSO; de cel kleurt binnen 5 seconden groen.',
      mbInformation, MB_OK);
  end;
end;

// --- Uninstall: remove firewall rule, and offer to keep or delete data ---
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  DataDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec('netsh', 'advfirewall firewall delete rule name="N1MM Field Day Tracker"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    DataDir := ExpandConstant('{localappdata}\N1MM Field Day Tracker');
    if DirExists(DataDir) then
    begin
      if MsgBox('Wil je ook alle velddaggegevens verwijderen?' + #13#10 + #13#10 +
                'Ja = alles wissen (QSO''s, velddagen, instellingen).' + #13#10 +
                'Nee = gegevens bewaren voor een latere herinstallatie.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;

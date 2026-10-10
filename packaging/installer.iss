; Installateur SmartScreen Hélio (écran 3,5" USB 0483:0065) + LibreHardwareMonitor
#define AppName "SmartScreen Helio"
#define AppVersion "1.0"

[Setup]
AppId={{6B7C2F1E-5A3D-4C8B-9E21-53A0C8D1F7A2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Hélio
AppCopyright=© 2026 Hélio - GPL-3.0
DefaultDirName=C:\SmartScreen Helio
DisableDirPage=no
DefaultGroupName={#AppName}
PrivilegesRequired=admin
OutputDir=..\..\Installateur
OutputBaseFilename=SmartScreenHelio_Setup_{#AppVersion}
SetupIconFile=..\res\icons\app.ico
UninstallDisplayIcon={app}\SmartScreen Helio.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"
Name: "autostart"; Description: "Lancer SmartScreen avec Windows (discret, près de l'horloge)"
Name: "lhmdl"; Description: "Télécharger LibreHardwareMonitor (nécessaire pour les températures, ~1 Mo, depuis github.com)"
Name: "lhmstart"; Description: "Lancer LibreHardwareMonitor avec Windows (températures)"; Flags: unchecked

[Dirs]
; dossier modifiable par l'utilisateur (thèmes, éditeur)
Name: "{app}"; Permissions: users-modify

[Files]
Source: "..\dist\SmartScreen Helio\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\SmartScreen Hélio"; Filename: "{app}\SmartScreen Helio.exe"
Name: "{group}\LibreHardwareMonitor"; Filename: "{app}\LibreHardwareMonitor\LibreHardwareMonitor.exe"
Name: "{group}\Désinstaller SmartScreen Hélio"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SmartScreen Hélio"; Filename: "{app}\SmartScreen Helio.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SmartScreenHelio"; ValueData: """{app}\SmartScreen Helio.exe"" --tray"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
; LibreHardwareMonitor démarre à l'ouverture de session avec les droits admin, sans fenêtre UAC
Filename: "schtasks.exe"; Parameters: "/Create /F /TN ""SmartScreenHelio_LibreHardwareMonitor"" /SC ONLOGON /RL HIGHEST /DELAY 0000:20 /TR ""\""{app}\LibreHardwareMonitor\LibreHardwareMonitor.exe\"""""; Flags: runhidden; Tasks: lhmstart; Check: LhmInstalled
Filename: "{app}\LibreHardwareMonitor\LibreHardwareMonitor.exe"; Description: "Lancer LibreHardwareMonitor maintenant"; Flags: shellexec nowait postinstall skipifsilent; Check: LhmInstalled
Filename: "{app}\SmartScreen Helio.exe"; Description: "Lancer SmartScreen Hélio"; Flags: nowait postinstall runasoriginaluser

[UninstallRun]
Filename: "schtasks.exe"; Parameters: "/Delete /F /TN ""SmartScreenHelio_LibreHardwareMonitor"""; Flags: runhidden; RunOnceId: "DelLHMTask"
Filename: "taskkill.exe"; Parameters: "/F /IM LibreHardwareMonitor.exe"; Flags: runhidden; RunOnceId: "KillLHM"
Filename: "taskkill.exe"; Parameters: "/F /IM ""SmartScreen Helio.exe"""; Flags: runhidden; RunOnceId: "KillSS"

[Code]
const
  LhmUrl = 'https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/latest/download/LibreHardwareMonitor.zip';

function LhmInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{app}\LibreHardwareMonitor\LibreHardwareMonitor.exe'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Dest, Zip, Ps: String;
  Code: Integer;
  Ok: Boolean;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('lhmdl') then
  begin
    Dest := ExpandConstant('{app}\LibreHardwareMonitor');
    Zip := ExpandConstant('{app}\LibreHardwareMonitor.zip');
    Ok := False;
    WizardForm.StatusLabel.Caption := 'Téléchargement de LibreHardwareMonitor (github.com)…';
    WizardForm.Refresh;
    Ps := '-NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; ' +
          '$ProgressPreference=''SilentlyContinue''; ' +
          'Invoke-WebRequest -UseBasicParsing -Uri ''' + LhmUrl + ''' -OutFile ''' + Zip + '''; ' +
          'New-Item -ItemType Directory -Force -Path ''' + Dest + ''' | Out-Null; ' +
          'Expand-Archive -LiteralPath ''' + Zip + ''' -DestinationPath ''' + Dest + ''' -Force; ' +
          'Remove-Item -LiteralPath ''' + Zip + ''' -Force"';
    if Exec('powershell.exe', Ps, '', SW_HIDE, ewWaitUntilTerminated, Code) then
      Ok := (Code = 0) and LhmInstalled;
    if not Ok then
      MsgBox('LibreHardwareMonitor n''a pas pu être téléchargé (pas de connexion, antivirus ou pare-feu).' + #13#10 +
             'Sans lui, les températures ne s''affichent pas.' + #13#10#13#10 +
             'Télécharge-le ici et décompresse-le dans :' + #13#10 + Dest + #13#10 +
             'https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases', mbInformation, MB_OK);
  end;
  // Active le serveur web de LibreHardwareMonitor (port 8085) : c'est lui que SmartScreen interroge
  if (CurStep = ssPostInstall) and LhmInstalled and
     not FileExists(ExpandConstant('{app}\LibreHardwareMonitor\LibreHardwareMonitor.config')) then
    SaveStringToFile(ExpandConstant('{app}\LibreHardwareMonitor\LibreHardwareMonitor.config'),
      '<?xml version="1.0" encoding="utf-8"?>' + #13#10 +
      '<configuration>' + #13#10 +
      '  <appSettings>' + #13#10 +
      '    <add key="startMinMenuItem" value="true" />' + #13#10 +
      '    <add key="minTrayMenuItem" value="true" />' + #13#10 +
      '    <add key="minCloseMenuItem" value="true" />' + #13#10 +
      '    <add key="runWebServerMenuItem" value="true" />' + #13#10 +
      '    <add key="listenerPort" value="8085" />' + #13#10 +
      '  </appSettings>' + #13#10 +
      '</configuration>' + #13#10, False);
end;

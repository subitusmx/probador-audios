; Probador de Audios — instalador de Windows (Inno Setup 6)
; Se compila en GitHub Actions:  iscc /DVersion=1.0.0 windows\ProbadorAudios.iss

#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{6F1C7A52-3B8E-4D1F-9C2A-5E7B8D9A0C11}
AppName=Probador de Audios
AppVersion={#Version}
AppVerName=Probador de Audios {#Version}
AppPublisher=Subitus
AppPublisherURL=https://github.com/subitusmx/probador-audios
DefaultDirName={localappdata}\Programs\ProbadorAudios
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ProbadorAudios-Windows-Setup
SetupIconFile=..\recursos\AppIcon.ico
UninstallDisplayIcon={app}\AppIcon.ico
UninstallDisplayName=Probador de Audios
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#ifdef Firmar
SignTool=firma $f
SignedUninstaller=yes
#endif

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el Escritorio"

[Files]
Source: "..\app\*"; DestDir: "{app}\app"; Excludes: "__pycache__"; Flags: recursesubdirs ignoreversion
Source: "iniciar.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\recursos\AppIcon.ico"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
Type: filesandordirs; Name: "{app}\app"

[Icons]
Name: "{autoprograms}\Probador de Audios"; Filename: "{app}\iniciar.bat"; WorkingDir: "{app}"; IconFilename: "{app}\AppIcon.ico"
Name: "{autodesktop}\Probador de Audios"; Filename: "{app}\iniciar.bat"; WorkingDir: "{app}"; IconFilename: "{app}\AppIcon.ico"; Tasks: escritorio

[Run]
Filename: "{app}\iniciar.bat"; Description: "Abrir Probador de Audios"; Flags: postinstall nowait skipifsilent shellexec

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Datos, Alterna: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Datos := ExpandConstant('{localappdata}\ProbadorAudios');
    Alterna := ExpandConstant('{sd}\ProbadorAudios');
    if DirExists(Datos) or DirExists(Alterna) then
    begin
      if UninstallSilent or (MsgBox('¿Borrar también el modelo de voz, los componentes y los proyectos guardados en la app?' + #13#10#13#10 +
         'Ocupan varios GB. Tus archivos de audio originales no se tocan.', mbConfirmation, MB_YESNO) = IDYES) then
      begin
        DelTree(Datos, True, True, True);
        DelTree(Alterna, True, True, True);
      end;
    end;
  end;
end;

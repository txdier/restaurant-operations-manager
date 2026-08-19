#define MyAppName "餐馆经营管理系统"
#define MyAppVersion "1.0.1"
#define MyAppExeName "RestaurantManager.exe"

[Setup]
AppId={{FA8B6680-81F5-4E78-BFA7-A2F6DB219142}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\RestaurantManager
DefaultGroupName={#MyAppName}
OutputDir=..\release
OutputBaseFilename=RestaurantManager-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
MinVersion=6.1sp1

[Files]
Source: "..\dist\RestaurantManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\RestaurantManagerUpdater.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "ApplyUpdate.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

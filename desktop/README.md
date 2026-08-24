# 餐馆经营管理系统 Windows 桌面版

正式版使用 64 位 Python 3.8.10、PyQt5 WebEngine 和 SQLite，支持 Windows 7 SP1、Windows 10、Windows 11。程序文件安装在当前用户目录，业务数据和个性化设置固定保存在 `%LOCALAPPDATA%\RestaurantManager`，卸载或增量更新不会覆盖账目数据库、名称、Logo 和桌面快捷方式设置。

## 构建安装包

在 64 位 Windows 上安装 Node.js 22、Python 3.8.10（64 位）和 Inno Setup 6，然后运行：

```bat
desktop\build_windows.bat
```

当前版本输出：`release\RestaurantManager-Setup-1.0.12.exe`。

## 更新检测

- 桌面版启动后延迟检查 GitHub 最新正式 Release，每 24 小时最多自动检查一次。
- 自动检查失败时保持静默，不影响离线使用；系统设置中可以手动检查并查看错误。
- 发现新版本时只在左侧版本号旁显示“有新版本”，点击后进入系统设置查看。
- “查看新版本”使用系统浏览器打开本仓库 Release 页面，由用户决定是否下载安装。

## 自定义名称与桌面图标

- 软件显示名称、窗口标题、界面 Logo、快捷方式名称和桌面图标均保存在数据库设置中。
- 上传的 PNG/JPG 桌面图片会转换为多尺寸 ICO，保存在 `%LOCALAPPDATA%\RestaurantManager\branding`。
- 程序每次启动以及更新后都会按用户设置同步桌面快捷方式，并清理本程序记录的旧名称快捷方式。
- `APP_ID`、安装目录和 `RestaurantManager.exe` 文件名保持固定，确保安装器和增量更新器始终能识别同一程序。

## 发布增量更新

完成修复后同步修改 `restaurant_manager/version.py`、`app-manifest.json` 与 `installer.iss` 的版本号，重新运行构建脚本，再生成更新包：

```bat
.venv-win7\Scripts\python desktop\make_update.py --version 1.0.1 --min-version 1.0.0
```

将 `RestaurantManager-Update-1.0.1.zip` 与 `RestaurantManagerUpdater.exe` 发给客户端。客户端关闭主程序后，把更新 ZIP 拖到 `ApplyUpdate.bat` 上即可；也可以运行：

```bat
RestaurantManagerUpdater.exe RestaurantManager-Update-1.0.1.zip --install-dir "%LOCALAPPDATA%\Programs\RestaurantManager"
```

更新器会校验每个文件、备份当前程序目录、替换程序文件并重新启动。用户数据不在安装目录中；数据库结构变化会在新版首次启动时自动迁移。复制失败时更新器自动还原原程序目录。

## 数据保护

- SQLite 使用 WAL 和事务写入。
- 恢复备份前先自动生成 `before_restore` 保护备份。
- 自动迁移始终保留旧字段并补充新字段。
- 自动备份每天首次启动且已超过设置时间时执行，按保留天数清理。
- 用户配置位于程序安装目录之外，覆盖安装和增量更新只替换程序文件。

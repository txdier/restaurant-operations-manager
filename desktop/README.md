# 餐馆经营管理系统 Windows 桌面版

正式版使用 64 位 Python 3.8.10、PyQt5 WebEngine 和 SQLite，支持 Windows 7 SP1、Windows 10、Windows 11。程序文件安装在当前用户目录，业务数据固定保存在 `%LOCALAPPDATA%\RestaurantManager`，卸载或增量更新不会覆盖账目数据库。

## 构建安装包

在 64 位 Windows 上安装 Node.js 22、Python 3.8.10（64 位）和 Inno Setup 6，然后运行：

```bat
desktop\build_windows.bat
```

当前版本输出：`release\RestaurantManager-Setup-1.0.8.exe`。

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

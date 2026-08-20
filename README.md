# 餐馆经营管理系统

面向小型餐馆的离线经营管理桌面应用，支持收入、销售、采购支出、商品、盘点、补货提醒、员工工资、供应商、装修设备、查询统计、数据导入导出和备份恢复。

## 主要特性

- 本地离线运行，账目数据使用 SQLite 保存。
- 管理员密码锁屏、启动自动锁定和无操作超时锁定。
- 可自定义软件显示名称、窗口标题、界面 Logo、桌面快捷方式名称和图标。
- 启动后每天最多自动检查一次 GitHub Release；发现新版本时仅在版本号旁显示轻量提醒。
- 支持手动检查更新、完整安装包和免重装增量更新包。

## Windows 版本

- 支持 Windows 7 SP1、Windows 10、Windows 11（64 位）。
- 业务数据与用户设置保存在 `%LOCALAPPDATA%\\RestaurantManager`。
- 自定义名称、Logo、桌面图标和快捷方式记录保存在用户数据目录，程序更新或重新安装后会自动恢复。
- 程序更新、重新安装或卸载不会主动删除业务数据库及用户设置。
- 支持完整安装包和免重装增量更新包。

## 下载安装包

可以进入仓库的 **Releases** 页面下载正式版本，或在 **Actions** 页面打开最新一次 **Build Windows Installer**，在页面底部下载 `RestaurantManager-Windows-x.x.x` 构建产物。

构建产物包含：

- `RestaurantManager-Setup-x.x.x.exe`：完整安装包
- `RestaurantManager-Update-x.x.x.zip`：增量更新包
- `RestaurantManagerUpdater.exe`：更新程序
- `ApplyUpdate.bat`：更新脚本

## 自动构建与发布

- 推送到 `main` 分支时，GitHub Actions 自动构建 Windows 安装包。
- 创建形如 `v1.0.0` 的 Git 标签时，自动创建 GitHub Release 并上传安装包和更新包。
- 也可以在 Actions 页面手动运行 **Build Windows Installer**。

更完整的构建、安装、数据存储和更新说明见 [desktop/README.md](desktop/README.md)。

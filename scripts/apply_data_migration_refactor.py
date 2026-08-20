from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"{label}: start marker not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"{label}: end marker not found")
    return text[:start] + replacement.rstrip() + "\n" + text[end:]


page_path = ROOT / "app" / "page.tsx"
page = page_path.read_text(encoding="utf-8")
page = replace_once(page, '["assets","♢","装修置物"]', '["assets","♢","资产与设备"]', "rename assets nav")
page = replace_once(
    page,
    'if(active==="assets")return <Assets assets={assets} setAssets={setAssets} expenses={expenses} toast={setToast}/>;',
    'if(active==="assets")return <Assets assets={assets} expenses={expenses} toast={setToast} go={go}/>;',
    "assets route",
)

assets_component = r'''function Assets({assets,expenses,toast,go}:any){
 const [tab,setTab]=useState<"asset"|"reno">("asset"),[status,setStatus]=useState("有效");
 const classify=(category:string):"asset"|"reno"|null=>category.includes("装修")?"reno":/(设备|置物|资产)/.test(category)?"asset":null;
 const rows=expenses.filter((e:Expense)=>classify(e.category)===tab&&(status==="全部"||e.status===status));
 const legacy=assets.filter((a:Asset)=>a.type===tab),totalAmount=rows.filter((e:Expense)=>e.status==="有效").reduce((sum:number,e:Expense)=>sum+e.amount,0);
 return <><Head title="资产与设备" desc="装修和设备信息直接来自采购与支出，避免同一笔费用重复录入"><Btn onClick={()=>go("expenses")}>＋ 前往采购与支出录入</Btn></Head><Tabs value={tab} set={setTab} items={[["asset","设备与置物"],["reno","装修支出"]]}/>
 <div className="panel asset-source-notice"><div><b>统一数据来源</b><span>本页不再单独新增账目。支出类别名称包含“装修”时归入装修支出；包含“设备 / 置物 / 资产”时归入设备与置物。修改、作废或导入支出后，本页会同步变化。</span></div><button className="link" onClick={()=>go("expenses")}>去录入支出 →</button></div>
 <div className="report asset-summary"><div><span>当前分类记录</span><b>{rows.length} 笔</b></div><div><span>有效支出合计</span><b>{money(totalAmount)}</b></div><div><span>数据来源</span><b>采购与支出</b></div><div><span>历史手工记录</span><b>{legacy.length} 条</b></div></div>
 <div className="filters asset-filters"><label>状态<select value={status} onChange={e=>setStatus(e.target.value)}><option>有效</option><option>已作废</option><option>全部</option></select></label><span className="info">这里是业务视图，不产生第二份支出数据。</span></div>
 <div className="panel"><table><thead><tr><th>日期</th><th>类别</th><th>项目 / 备注</th><th>金额</th><th>经手人</th><th>状态</th><th>来源</th></tr></thead><tbody>{rows.map((e:Expense)=><tr key={e.id} className={e.status!=="有效"?"void":""}><td>{e.date}</td><td>{e.category}</td><td><b>{e.item}</b></td><td><b>{money(e.amount)}</b></td><td>{e.handler}</td><td><span className="tag">{e.status}</span></td><td><span className="yes">采购与支出</span></td></tr>)}</tbody></table>{!rows.length&&<div className="empty-state">暂无匹配的{tab==="asset"?"设备与置物":"装修"}支出。请在“采购与支出”中选择对应类别录入。</div>}</div>
 {legacy.length>0&&<Panel title="历史手工记录" sub="旧版本兼容，只读保留"><div className="legacy-assets-note">这些记录来自旧版“装修置物”的独立录入。为避免与支出账重复，本版本不再允许在此新增或修改；需要继续记账时请使用“采购与支出”。</div><table><thead><tr><th>名称</th><th>数量</th><th>日期</th><th>金额</th><th>状态</th><th>备注</th></tr></thead><tbody>{legacy.map((a:Asset)=><tr key={a.id}><td><b>{a.name}</b></td><td>{a.qty} {a.unit}</td><td>{a.date}</td><td>{money(a.amount)}</td><td><span className="tag">{a.status}</span></td><td>{a.note}</td></tr>)}</tbody></table></Panel>}
 </>}
'''
page = replace_block(page, "function Assets(", "function Reports(", assets_component, "assets component")

page = page.replace(
    'Head title="数据导入" desc="通过 Excel 批量导入快速支出和详细采购"',
    'Head title="业务数据导入" desc="通过 Excel 批量导入支出业务；完整系统迁移请到“备份恢复”"',
)
page = page.replace(
    'Head title="数据导出" desc="导出全局经营数据，不包含单页查询结果"',
    'Head title="业务数据导出" desc="用于报表、归档和二次处理；完整系统迁移请使用迁移包"',
)
page = page.replace(
    '各类数据分别生成 UTF-8 CSV 后打包，适合迁移或二次处理。',
    '各类数据分别生成 UTF-8 CSV 后打包，适合归档或二次处理，不用于系统恢复。',
)

backup_component = r'''function BackupReal({settings,setSettings,toast}:any){
 const [items,setItems]=useState<any[]>([]),[showSettings,setShowSettings]=useState(true),[busy,setBusy]=useState(false),[migrationBusy,setMigrationBusy]=useState(false),[migrationPath,setMigrationPath]=useState(""),[migrationInfo,setMigrationInfo]=useState<any>(null);
 const refresh=async()=>{if(!isDesktop())return;try{const result=await desktopRequest<{items:any[]}>("backups");setItems(result.items)}catch(e:any){toast(e.message)}};
 useEffect(()=>{refresh()},[]);
 const backup=async()=>{if(!isDesktop())return toast("备份与恢复请在 Windows 桌面版中使用");setBusy(true);try{const result=await desktopRequest<{items:any[]}>("backup",{method:"POST",body:JSON.stringify({targetDir:settings.backupDir})});setItems(result.items);toast("备份已完成")}catch(e:any){toast(`备份失败：${e.message}`)}finally{setBusy(false)}};
 const restore=async(path:string)=>{if(!confirm("恢复后，当前数据将先自动生成一份保护备份，再替换为所选备份。确认继续？"))return;setBusy(true);try{await desktopRequest("restore",{method:"POST",body:JSON.stringify({path})});toast("恢复成功，程序将在刷新后显示备份数据");setTimeout(()=>location.reload(),800)}catch(e:any){toast(`恢复失败：${e.message}`)}finally{setBusy(false)}};
 const selectDir=async()=>{try{const result=await desktopRequest<{path:string}>("select-directory",{method:"POST",body:"{}"});if(result.path)setSettings({...settings,backupDir:result.path})}catch(e:any){toast(e.message)}};
 const openDir=async()=>{try{const path=settings.backupDir||(await desktopRequest<{backupDir:string}>("meta")).backupDir;await desktopRequest("open-directory",{method:"POST",body:JSON.stringify({path})})}catch(e:any){toast(e.message)}};
 const exportMigration=async()=>{if(!isDesktop())return toast("系统迁移请在 Windows 桌面版中使用");setMigrationBusy(true);try{const result=await desktopRequest<{path:string;manifest:any}>("migration/export",{method:"POST",body:"{}"});if(result.path)toast(`系统迁移包已导出：${result.path}`)}catch(e:any){toast(`迁移包导出失败：${e.message}`)}finally{setMigrationBusy(false)}};
 const chooseMigration=async()=>{if(!isDesktop())return toast("系统迁移请在 Windows 桌面版中使用");setMigrationBusy(true);try{const selected=await desktopRequest<{path:string}>("migration/select",{method:"POST",body:"{}"});if(!selected.path)return;const inspected=await desktopRequest<{manifest:any}>("migration/inspect",{method:"POST",body:JSON.stringify({path:selected.path})});setMigrationPath(selected.path);setMigrationInfo(inspected.manifest);toast("迁移包校验通过，可执行导入")}catch(e:any){setMigrationPath("");setMigrationInfo(null);toast(`迁移包检查失败：${e.message}`)}finally{setMigrationBusy(false)}};
 const importMigration=async()=>{if(!migrationPath||!migrationInfo)return toast("请先选择并校验迁移包");if(!confirm(`确认导入这个系统迁移包？\n\n来源版本：v${migrationInfo.appVersion||"未知"}\n数据版本：${migrationInfo.schemaVersion}\n生成时间：${migrationInfo.createdAt||"未知"}\n\n当前数据库会先自动生成保护备份，然后再恢复迁移包。`))return;setMigrationBusy(true);try{await desktopRequest("migration/import",{method:"POST",body:JSON.stringify({path:migrationPath})});toast("系统迁移完成，正在重新载入数据");setTimeout(()=>location.reload(),900)}catch(e:any){toast(`系统迁移失败：${e.message}`)}finally{setMigrationBusy(false)}};
 const size=(n:number)=>n>1048576?`${(n/1048576).toFixed(1)} MB`:`${Math.ceil(n/1024)} KB`;
 return <><Head title="备份与恢复" desc="本机备份用于日常恢复；系统迁移包用于完整迁移到另一台电脑"/><div className="actions"><button onClick={backup} disabled={busy}><b>☁</b><span><strong>{busy?"处理中…":"立即备份"}</strong><small>创建当前数据库备份</small></span></button><button onClick={()=>items[0]?restore(items[0].path):toast("当前没有可恢复的备份")} disabled={busy}><b>↶</b><span><strong>恢复最近备份</strong><small>恢复前自动保护当前数据</small></span></button><button onClick={openDir}><b>▰</b><span><strong>打开备份目录</strong><small>{settings.backupDir||"默认本地备份目录"}</small></span></button><button className={showSettings?"selected":""} onClick={()=>setShowSettings(!showSettings)}><b>⚙</b><span><strong>备份设置</strong><small>目录、时间与保留期限</small></span></button></div>
 <div className="panel migration-panel"><div className="pt"><b>系统迁移</b><span>完整数据库迁移，不使用 Excel 还原系统</span></div><div className="migration-body"><div className="migration-guide"><b>旧电脑：导出迁移包</b><span>生成包含完整 SQLite 数据库和版本校验信息的 ZIP；收入、支出、商品、工资、供应商、设置、Logo 等随数据库一起迁移。</span></div><div className="migration-guide"><b>新电脑：选择并导入迁移包</b><span>导入前校验格式、SHA-256 和数据版本，并自动备份新电脑当前数据库；旧版本数据会按现有数据库迁移机制升级。</span></div><div className="migration-buttons"><Btn soft onClick={()=>!migrationBusy&&exportMigration()}>{migrationBusy?"处理中…":"导出系统迁移包"}</Btn><Btn soft onClick={()=>!migrationBusy&&chooseMigration()}>{migrationBusy?"处理中…":"选择迁移包…"}</Btn></div>{migrationPath&&<div className="migration-selected"><span>已选择</span><b title={migrationPath}>{migrationPath}</b></div>}{migrationInfo&&<div className="migration-check"><div><span>来源软件版本</span><b>v{migrationInfo.appVersion||"未知"}</b></div><div><span>数据版本</span><b>{migrationInfo.schemaVersion}</b></div><div><span>生成时间</span><b>{migrationInfo.createdAt||"未知"}</b></div><Btn onClick={()=>!migrationBusy&&importMigration()}>导入并完整恢复</Btn></div>}<small className="muted">业务 Excel / CSV 仍用于报表和批量业务录入，不作为完整系统恢复格式。日志和历史备份文件不会打包进迁移包。</small></div></div>
 {showSettings&&<div className="panel backup-settings"><div className="pt"><b>备份设置</b><span>修改后自动保存</span></div><div className="backup-form"><label>备份目录<div className="directory-input"><input value={settings.backupDir} onChange={e=>setSettings({...settings,backupDir:e.target.value})} placeholder="留空使用默认目录"/><button onClick={selectDir}>选择目录…</button></div><small>建议选择非系统盘或移动硬盘；目录不存在时会自动创建。</small></label><label>每日自动备份时间<input type="time" value={settings.backupTime} onChange={e=>setSettings({...settings,backupTime:e.target.value})}/></label><label>备份保留天数<div className="suffix-input"><input type="number" min="7" value={settings.backupKeepDays} onChange={e=>setSettings({...settings,backupKeepDays:Math.max(7,Number(e.target.value))})}/><span>天</span></div></label></div></div>}<div className="panel backup-list"><div className="pt"><b>备份文件列表</b><button className="link" onClick={refresh}>刷新</button></div><table><thead><tr><th>文件名称</th><th>备份时间</th><th>类型</th><th>大小</th><th>操作</th></tr></thead><tbody>{items.map(item=><tr key={item.path}><td><b>{item.name}</b></td><td>{item.time}</td><td><span className="tag">{item.kind}</span></td><td>{size(item.size)}</td><td><button className="link" disabled={busy} onClick={()=>restore(item.path)}>恢复</button></td></tr>)}</tbody></table>{!items.length&&<div className="empty-state">暂无备份文件。</div>}</div></>
}
'''
page = replace_block(page, "function BackupReal(", "function SettingsReal(", backup_component, "backup component")
page_path.write_text(page, encoding="utf-8")

layout_path = ROOT / "app" / "layout.tsx"
layout = layout_path.read_text(encoding="utf-8")
layout = replace_once(layout, 'import "./branding.css";', 'import "./branding.css";\nimport "./tabs-enhanced.css";\nimport "./asset-view.css";\nimport "./migration.css";', "layout css imports")
layout_path.write_text(layout, encoding="utf-8")

(ROOT / "app" / "tabs-enhanced.css").write_text(r'''.tabs{display:flex;width:fit-content;max-width:100%;gap:4px;padding:4px;margin-bottom:16px;border:1px solid #dce4ec;border-radius:9px;background:#edf2f6;overflow-x:auto}.tabs button{flex:0 0 auto;min-height:38px;padding:8px 16px;border:1px solid transparent!important;border-radius:6px;background:transparent;color:#5f6d80;font-weight:500;transition:background .16s,border-color .16s,color .16s,box-shadow .16s}.tabs button:hover{background:#f8fbfd;color:#304257}.tabs button.on{background:#fff;color:#078c6a;border-color:#bcded3!important;font-weight:700;box-shadow:0 2px 7px #20364a14}.tabs button.on:focus-visible{outline:2px solid #11ad84;outline-offset:1px}@media(max-width:760px){.tabs{width:100%}.tabs button{padding:8px 13px}}
''', encoding="utf-8")

(ROOT / "app" / "asset-view.css").write_text(r'''.asset-source-notice{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:16px 18px;margin-bottom:14px;border-left:4px solid #11ad84}.asset-source-notice>div{display:flex;flex-direction:column;gap:5px}.asset-source-notice span{color:#6f7d90;line-height:1.6}.asset-summary{margin-bottom:14px}.asset-filters{justify-content:flex-start}.legacy-assets-note{padding:14px 16px;background:#fff8e8;color:#785d20;border-bottom:1px solid #efe4c8;line-height:1.7}@media(max-width:760px){.asset-source-notice{align-items:flex-start;flex-direction:column}}
''', encoding="utf-8")

(ROOT / "app" / "migration.css").write_text(r'''.migration-panel{margin-bottom:14px}.migration-body{padding:18px}.migration-guide{display:grid;grid-template-columns:190px 1fr;gap:16px;padding:11px 0;border-bottom:1px solid #eef2f5}.migration-guide span{color:#6f7d90;line-height:1.65}.migration-buttons{display:flex;gap:10px;margin:18px 0}.migration-selected{display:flex;align-items:center;gap:10px;padding:10px 12px;background:#f5f8fb;border:1px solid #e1e7ed;border-radius:7px}.migration-selected span{color:#7a8798}.migration-selected b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.migration-check{display:grid;grid-template-columns:repeat(3,minmax(0,1fr)) auto;align-items:end;gap:10px;margin:12px 0}.migration-check>div{display:flex;flex-direction:column;gap:5px;padding:10px 12px;border:1px solid #e1e7ed;border-radius:7px;background:#fff}.migration-check span{font-size:11px;color:#7c8999}.migration-check b{font-size:13px;overflow:hidden;text-overflow:ellipsis}.migration-body>.muted{display:block;margin-top:14px;line-height:1.6}@media(max-width:900px){.migration-guide{grid-template-columns:1fr;gap:4px}.migration-check{grid-template-columns:1fr 1fr}.migration-check>.btn{grid-column:1/-1}}@media(max-width:600px){.migration-buttons{flex-direction:column}.migration-check{grid-template-columns:1fr}}
''', encoding="utf-8")

migration_module = r'''from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .database import Database
from .version import APP_NAME, APP_VERSION, DATA_SCHEMA_VERSION

MIGRATION_FORMAT = "restaurant-manager-migration"
MIGRATION_FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
DATABASE_NAME = "restaurant.db"
MAX_DATABASE_SIZE = 1024 * 1024 * 1024
MAX_MANIFEST_SIZE = 128 * 1024


def _sha256_stream(stream: Any) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _manifest(schema_version: int, database_hash: str) -> Dict[str, Any]:
    return {
        "format": MIGRATION_FORMAT,
        "formatVersion": MIGRATION_FORMAT_VERSION,
        "appName": APP_NAME,
        "appVersion": APP_VERSION,
        "schemaVersion": schema_version,
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "database": {"path": DATABASE_NAME, "sha256": database_hash},
    }


def export_migration_package(database: Database, target: Path) -> Dict[str, Any]:
    if target.suffix.lower() != ".zip":
        target = target.with_suffix(".zip")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="restaurant-migration-export-") as temp_dir:
        snapshot = database.backup(Path(temp_dir), "migration")
        with snapshot.open("rb") as handle:
            database_hash = _sha256_stream(handle)
        manifest = _manifest(DATA_SCHEMA_VERSION, database_hash)
        with zipfile.ZipFile(str(target), "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.write(str(snapshot), DATABASE_NAME)
    return manifest


def inspect_migration_package(source: Path) -> Dict[str, Any]:
    if not source.exists() or source.suffix.lower() != ".zip":
        raise ValueError("请选择有效的 .zip 系统迁移包")
    if not zipfile.is_zipfile(str(source)):
        raise ValueError("迁移包不是有效的 ZIP 文件")
    with zipfile.ZipFile(str(source), "r") as archive:
        names = set(archive.namelist())
        if MANIFEST_NAME not in names or DATABASE_NAME not in names:
            raise ValueError("迁移包缺少 manifest.json 或 restaurant.db")
        if archive.getinfo(MANIFEST_NAME).file_size > MAX_MANIFEST_SIZE:
            raise ValueError("迁移包清单大小异常")
        if archive.getinfo(DATABASE_NAME).file_size > MAX_DATABASE_SIZE:
            raise ValueError("迁移包数据库超过 1 GB，已拒绝导入")
        try:
            manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("迁移包清单无法读取") from error
        if manifest.get("format") != MIGRATION_FORMAT:
            raise ValueError("该文件不是本系统生成的迁移包")
        if int(manifest.get("formatVersion", 0)) != MIGRATION_FORMAT_VERSION:
            raise ValueError("暂不支持该迁移包格式，请先升级软件")
        try:
            schema_version = int(manifest.get("schemaVersion", 0))
        except (TypeError, ValueError) as error:
            raise ValueError("迁移包数据版本无效") from error
        if schema_version <= 0:
            raise ValueError("迁移包数据版本无效")
        if schema_version > DATA_SCHEMA_VERSION:
            raise ValueError("迁移包来自更高的数据版本，请先把当前软件升级到不低于来源电脑的版本后再导入")
        expected_hash = str(manifest.get("database", {}).get("sha256", "")).lower()
        if len(expected_hash) != 64:
            raise ValueError("迁移包数据库校验信息缺失")
        with archive.open(DATABASE_NAME, "r") as database_stream:
            actual_hash = _sha256_stream(database_stream)
        if actual_hash != expected_hash:
            raise ValueError("迁移包数据库校验失败，文件可能不完整或已损坏")
    return manifest


def import_migration_package(database: Database, source: Path, safety_dir: Path) -> Dict[str, Any]:
    manifest = inspect_migration_package(source)
    safety_dir.mkdir(parents=True, exist_ok=True)
    safety_backup = database.backup(safety_dir, "before_migration")
    with tempfile.TemporaryDirectory(prefix="restaurant-migration-import-") as temp_dir:
        candidate = Path(temp_dir) / DATABASE_NAME
        with zipfile.ZipFile(str(source), "r") as archive:
            with archive.open(DATABASE_NAME, "r") as src, candidate.open("wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
        database.restore(candidate)
    return {"manifest": manifest, "safetyBackup": str(safety_backup)}
'''
(ROOT / "desktop" / "restaurant_manager" / "migration_package.py").write_text(migration_module, encoding="utf-8")

server_path = ROOT / "desktop" / "restaurant_manager" / "server.py"
server = server_path.read_text(encoding="utf-8")
server = replace_once(
    server,
    'from .importer import apply_import, create_import_template, preview_import\n',
    'from .importer import apply_import, create_import_template, preview_import\nfrom .migration_package import export_migration_package, import_migration_package, inspect_migration_package\n',
    "migration imports",
)
server_marker = '            if self.path == "/api/import/template":\n'
migration_endpoints = r'''            if self.path == "/api/migration/export":
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                selected = windows_dialog(
                    "$d=New-Object System.Windows.Forms.SaveFileDialog;"
                    "$d.Title='导出餐馆系统迁移包';"
                    "$d.Filter='系统迁移包 (*.zip)|*.zip';$d.DefaultExt='zip';$d.AddExtension=$true;"
                    f"$d.FileName='餐馆系统迁移包_{stamp}.zip';"
                    "if($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK){$result=$d.FileName};"
                    "$d.Dispose();$owner.Dispose()"
                )
                if not selected:
                    return self._json({"ok": True, "path": "", "cancelled": True})
                target = Path(selected)
                manifest = export_migration_package(self.service.database, target)
                return self._json({"ok": True, "path": str(target), "manifest": manifest})
            if self.path == "/api/migration/select":
                selected = windows_dialog(
                    "$d=New-Object System.Windows.Forms.OpenFileDialog;"
                    "$d.Title='选择餐馆系统迁移包';"
                    "$d.Filter='系统迁移包 (*.zip)|*.zip';$d.Multiselect=$false;"
                    "if($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK){$result=$d.FileName};"
                    "$d.Dispose();$owner.Dispose()"
                )
                return self._json({"ok": True, "path": selected})
            if self.path == "/api/migration/inspect":
                source = Path(str(body.get("path", "")))
                return self._json({"ok": True, "manifest": inspect_migration_package(source)})
            if self.path == "/api/migration/import":
                source = Path(str(body.get("path", "")))
                result = import_migration_package(self.service.database, source, self.service._backup_dir())
                return self._json({"ok": True, **result, "state": self._public_state(self.service.database.load())})
'''
if server.count(server_marker) != 1:
    raise RuntimeError("server migration insertion marker mismatch")
server = server.replace(server_marker, migration_endpoints + server_marker, 1)
server_path.write_text(server, encoding="utf-8")

version_path = ROOT / "desktop" / "restaurant_manager" / "version.py"
version = version_path.read_text(encoding="utf-8")
version = replace_once(version, 'APP_VERSION = "1.0.9"', 'APP_VERSION = "1.0.10"', "python app version")
version_path.write_text(version, encoding="utf-8")

manifest_path = ROOT / "desktop" / "app-manifest.json"
manifest = manifest_path.read_text(encoding="utf-8")
manifest = replace_once(manifest, '"version": "1.0.9"', '"version": "1.0.10"', "manifest app version")
manifest_path.write_text(manifest, encoding="utf-8")

readme_path = ROOT / "README.md"
readme = readme_path.read_text(encoding="utf-8")
readme = replace_once(
    readme,
    '- 支持手动检查更新、完整安装包和免重装增量更新包。',
    '- 支持手动检查更新、完整安装包和免重装增量更新包。\n- “资产与设备”直接汇总“采购与支出”中的装修、设备/置物类支出，避免重复记账。\n- 业务 Excel/CSV 与系统迁移分离：跨电脑迁移使用带版本与 SHA-256 校验的完整数据库迁移包。',
    "readme features",
)
readme_path.write_text(readme, encoding="utf-8")

test_path = ROOT / "desktop" / "tests" / "test_migration_package.py"
test_path.write_text(r'''import json
import zipfile
from pathlib import Path

import pytest

from restaurant_manager.database import Database
from restaurant_manager.migration_package import export_migration_package, import_migration_package, inspect_migration_package


def test_migration_package_round_trip(tmp_path: Path) -> None:
    source_db = Database(tmp_path / "source.db")
    state = source_db.load()
    state["expenses"] = [{"id": 9, "date": "2026-08-20", "mode": "快速记账", "category": "装修", "item": "后厨改造", "amount": 8800, "handler": "老板", "status": "有效"}]
    state["settings"]["storeName"] = "迁移测试餐馆"
    source_db.save(state, "test_seed")

    package = tmp_path / "migration.zip"
    manifest = export_migration_package(source_db, package)
    assert package.exists()
    assert manifest["format"] == "restaurant-manager-migration"
    inspected = inspect_migration_package(package)
    assert inspected["database"]["sha256"] == manifest["database"]["sha256"]

    target_db = Database(tmp_path / "target.db")
    import_migration_package(target_db, package, tmp_path / "safety")
    restored = target_db.load()
    assert restored["settings"]["storeName"] == "迁移测试餐馆"
    assert restored["expenses"][0]["item"] == "后厨改造"
    assert list((tmp_path / "safety").glob("restaurant_*_before_migration.db"))


def test_migration_package_rejects_tampered_database(tmp_path: Path) -> None:
    database = Database(tmp_path / "source.db")
    package = tmp_path / "migration.zip"
    export_migration_package(database, package)
    broken = tmp_path / "broken.zip"
    with zipfile.ZipFile(package, "r") as src, zipfile.ZipFile(broken, "w") as dst:
        dst.writestr("manifest.json", src.read("manifest.json"))
        dst.writestr("restaurant.db", src.read("restaurant.db") + b"tampered")
    with pytest.raises(ValueError, match="校验失败"):
        inspect_migration_package(broken)
''', encoding="utf-8")

# This script is only a transport helper for applying the refactor through CI.
# Remove it and its temporary workflow from the final source tree.
Path(__file__).unlink()
workflow = ROOT / ".github" / "workflows" / "apply-data-migration-refactor.yml"
if workflow.exists():
    workflow.unlink()

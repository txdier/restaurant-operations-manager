"use client";

import {useEffect,useMemo,useState} from "react";
import {createPortal} from "react-dom";
import {desktopRequest,isDesktop,loadDesktopState} from "./desktop-api";

type Expense={id:number|string;date:string;mode:string;category:string;item:string;amount:number;handler:string;status:string};
type LegacyAsset={id:number|string;name:string;qty:number;unit:string;date:string;amount:number;status:string;note:string;type:"asset"|"reno"};
type MigrationManifest={appVersion?:string;schemaVersion:number;createdAt?:string;formatVersion:number};

type ActiveView=""|"assets"|"backup"|"import"|"export";

const money=(value:number)=>`¥ ${Number(value||0).toLocaleString("zh-CN",{minimumFractionDigits:2})}`;

function detectView():ActiveView{
 const button=document.querySelector(".side nav button.active") as HTMLButtonElement|null;
 const title=button?.getAttribute("title")||button?.textContent||"";
 if(title.includes("装修置物")||title.includes("资产与设备"))return "assets";
 if(title.includes("备份恢复")||title.includes("备份与恢复"))return "backup";
 if(title.includes("数据导入")||title.includes("业务数据导入"))return "import";
 if(title.includes("数据导出")||title.includes("业务数据导出"))return "export";
 return "";
}

function renameAssetsNavigation(){
 const button=Array.from(document.querySelectorAll(".side nav button")).find((item)=>item.getAttribute("title")==="装修置物") as HTMLButtonElement|undefined;
 if(button){
  button.title="资产与设备";
  for(const node of Array.from(button.childNodes))if(node.nodeType===Node.TEXT_NODE&&node.textContent?.includes("装修置物"))node.textContent="资产与设备";
 }
 const active=button?.classList.contains("active");
 if(active){
  const headerTitle=document.querySelector("main>header>div:first-child>b");
  if(headerTitle&&headerTitle.textContent==="装修置物")headerTitle.textContent="资产与设备";
 }
}

function ensureHost(view:ActiveView):HTMLElement|null{
 const content=document.querySelector("section.content") as HTMLElement|null;
 if(!content)return null;
 let host=content.querySelector(":scope > .runtime-enhancement-host") as HTMLElement|null;
 if(!host){host=document.createElement("div");host.className="runtime-enhancement-host";content.appendChild(host)}
 if(view==="backup"){
  const actions=content.querySelector(":scope > .actions");
  if(actions&&actions.nextElementSibling!==host)actions.insertAdjacentElement("afterend",host);
 }else if(view==="assets"&&content.lastElementChild!==host){content.appendChild(host)}
 return host;
}

function goTo(title:string){
 const target=Array.from(document.querySelectorAll(".side nav button")).find((item)=>item.getAttribute("title")===title||item.textContent?.includes(title)) as HTMLButtonElement|undefined;
 target?.click();
}

function UnifiedAssetView(){
 const [state,setState]=useState<any>(null),[tab,setTab]=useState<"asset"|"reno">("asset"),[status,setStatus]=useState("有效"),[error,setError]=useState("");
 useEffect(()=>{
  let stopped=false;
  const load=async()=>{try{const next=isDesktop()?await loadDesktopState():JSON.parse(localStorage.getItem("restaurant-v1")||"null");if(!stopped)setState(next||{})}catch(e:any){if(!stopped)setError(e.message||"读取数据失败")}};
  load();const timer=setInterval(load,1000);return()=>{stopped=true;clearInterval(timer)};
 },[]);
 const classify=(category:string):"asset"|"reno"|null=>category.includes("装修")?"reno":/(设备|置物|资产)/.test(category)?"asset":null;
 const expenses:Expense[]=state?.expenses||[],legacy:LegacyAsset[]=state?.assets||[];
 const rows=useMemo(()=>expenses.filter((row)=>classify(row.category)===tab&&(status==="全部"||row.status===status)),[expenses,tab,status]);
 const legacyRows=legacy.filter((row)=>row.type===tab),total=rows.filter((row)=>row.status==="有效").reduce((sum,row)=>sum+Number(row.amount||0),0);
 return <div className="runtime-assets-view">
  <div className="head"><div><h1>资产与设备</h1><p>装修和设备信息直接来自采购与支出，避免同一笔费用重复录入</p></div><div><button className="btn" onClick={()=>goTo("采购与支出")}>＋ 前往采购与支出录入</button></div></div>
  <div className="tabs enhanced-tabs"><button className={tab==="asset"?"on":""} onClick={()=>setTab("asset")}>设备与置物</button><button className={tab==="reno"?"on":""} onClick={()=>setTab("reno")}>装修支出</button></div>
  <div className="panel asset-source-notice"><div><b>统一数据来源</b><span>本页不再单独新增账目。类别名称包含“装修”时归入装修支出；包含“设备 / 置物 / 资产”时归入设备与置物。修改、作废或导入支出后，这里会自动同步。</span></div><button className="link" onClick={()=>goTo("采购与支出")}>去录入支出 →</button></div>
  {error&&<div className="warn runtime-error">{error}</div>}
  <div className="report asset-summary"><div><span>当前分类记录</span><b>{rows.length} 笔</b></div><div><span>有效支出合计</span><b>{money(total)}</b></div><div><span>数据来源</span><b>采购与支出</b></div><div><span>历史手工记录</span><b>{legacyRows.length} 条</b></div></div>
  <div className="filters asset-filters"><label>状态<select value={status} onChange={(e)=>setStatus(e.target.value)}><option>有效</option><option>已作废</option><option>全部</option></select></label><span className="info">这里是业务视图，不产生第二份支出数据。</span></div>
  <div className="panel"><table><thead><tr><th>日期</th><th>类别</th><th>项目 / 备注</th><th>金额</th><th>经手人</th><th>状态</th><th>来源</th></tr></thead><tbody>{rows.map((row)=><tr key={String(row.id)} className={row.status!=="有效"?"void":""}><td>{row.date}</td><td>{row.category}</td><td><b>{row.item}</b></td><td><b>{money(row.amount)}</b></td><td>{row.handler}</td><td><span className="tag">{row.status}</span></td><td><span className="yes">采购与支出</span></td></tr>)}</tbody></table>{!rows.length&&<div className="empty-state">暂无匹配的{tab==="asset"?"设备与置物":"装修"}支出。请在“采购与支出”中选择对应类别录入。</div>}</div>
  {legacyRows.length>0&&<article className="panel legacy-assets"><div className="pt"><b>历史手工记录</b><span>旧版本兼容，只读保留</span></div><div className="legacy-assets-note">这些记录来自旧版“装修置物”的独立录入。为避免与支出账重复，本版本不再允许在此新增或修改；后续统一在“采购与支出”记录。</div><table><thead><tr><th>名称</th><th>数量</th><th>日期</th><th>金额</th><th>状态</th><th>备注</th></tr></thead><tbody>{legacyRows.map((row)=><tr key={String(row.id)}><td><b>{row.name}</b></td><td>{row.qty} {row.unit}</td><td>{row.date}</td><td>{money(row.amount)}</td><td><span className="tag">{row.status}</span></td><td>{row.note}</td></tr>)}</tbody></table></article>}
 </div>
}

function MigrationPanel(){
 const [busy,setBusy]=useState(false),[path,setPath]=useState(""),[manifest,setManifest]=useState<MigrationManifest|null>(null),[message,setMessage]=useState("");
 const exportPackage=async()=>{if(!isDesktop())return setMessage("系统迁移仅在 Windows 桌面版中可用");setBusy(true);setMessage("");try{const result=await desktopRequest<{path:string}>("migration/export",{method:"POST",body:"{}"});if(result.path)setMessage(`迁移包已导出：${result.path}`)}catch(e:any){setMessage(`导出失败：${e.message}`)}finally{setBusy(false)}};
 const choosePackage=async()=>{if(!isDesktop())return setMessage("系统迁移仅在 Windows 桌面版中可用");setBusy(true);setMessage("");try{const selected=await desktopRequest<{path:string}>("migration/select",{method:"POST",body:"{}"});if(!selected.path)return;const checked=await desktopRequest<{manifest:MigrationManifest}>("migration/inspect",{method:"POST",body:JSON.stringify({path:selected.path})});setPath(selected.path);setManifest(checked.manifest);setMessage("迁移包校验通过，可以导入") }catch(e:any){setPath("");setManifest(null);setMessage(`检查失败：${e.message}`)}finally{setBusy(false)}};
 const importPackage=async()=>{if(!path||!manifest)return;const ok=confirm(`确认导入这个系统迁移包？\n\n来源版本：v${manifest.appVersion||"未知"}\n数据版本：${manifest.schemaVersion}\n生成时间：${manifest.createdAt||"未知"}\n\n当前数据库会先自动生成保护备份，然后再恢复迁移包。`);if(!ok)return;setBusy(true);setMessage("");try{await desktopRequest("migration/import",{method:"POST",body:JSON.stringify({path})});setMessage("系统迁移完成，正在重新载入数据");setTimeout(()=>location.reload(),900)}catch(e:any){setMessage(`导入失败：${e.message}`)}finally{setBusy(false)}};
 return <div className="panel migration-panel"><div className="pt"><b>系统迁移</b><span>完整数据库迁移，不使用 Excel 还原系统</span></div><div className="migration-body"><div className="migration-guide"><b>旧电脑：导出迁移包</b><span>生成完整 SQLite 数据库和版本校验信息。收入、支出、商品、工资、供应商、系统设置、Logo 等会随数据库一起迁移。</span></div><div className="migration-guide"><b>新电脑：选择并导入迁移包</b><span>导入前检查格式、SHA-256 和数据版本，并自动备份新电脑当前数据库；较旧的数据结构会通过现有 Migration 机制升级。</span></div><div className="migration-buttons"><button className="btn soft" disabled={busy} onClick={exportPackage}>{busy?"处理中…":"导出系统迁移包"}</button><button className="btn soft" disabled={busy} onClick={choosePackage}>{busy?"处理中…":"选择迁移包…"}</button></div>{path&&<div className="migration-selected"><span>已选择</span><b title={path}>{path}</b></div>}{manifest&&<div className="migration-check"><div><span>来源软件版本</span><b>v{manifest.appVersion||"未知"}</b></div><div><span>数据版本</span><b>{manifest.schemaVersion}</b></div><div><span>生成时间</span><b>{manifest.createdAt||"未知"}</b></div><button className="btn" disabled={busy} onClick={importPackage}>导入并完整恢复</button></div>}{message&&<div className={message.includes("失败")?"warn migration-message":"info migration-message"}>{message}</div>}<small className="muted migration-footnote">业务 Excel / CSV 仍用于报表和批量业务录入，不作为完整系统恢复格式。日志和历史备份文件不会打包进迁移包。</small></div></div>
}

export default function RuntimeEnhancements(){
 const [view,setView]=useState<ActiveView>("");const [host,setHost]=useState<HTMLElement|null>(null);
 useEffect(()=>{
  let last="";
  const sync=()=>{renameAssetsNavigation();const next=detectView();if(next!==last){last=next;setView(next)};const content=document.querySelector("section.content");content?.classList.toggle("runtime-assets-active",next==="assets");setHost((next==="assets"||next==="backup")?ensureHost(next):null)};
  sync();const observer=new MutationObserver(sync);observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:["class"]});const timer=setInterval(sync,700);return()=>{observer.disconnect();clearInterval(timer);document.querySelector("section.content")?.classList.remove("runtime-assets-active")};
 },[]);
 useEffect(()=>{
  const content=document.querySelector("section.content");if(!content)return;
  const head=content.querySelector(":scope > .head");
  if(view==="import"&&head){const h=head.querySelector("h1"),p=head.querySelector("p");if(h)h.textContent="业务数据导入";if(p)p.textContent="通过 Excel 批量导入支出业务；完整系统迁移请到“备份恢复”"}
  if(view==="export"&&head){const h=head.querySelector("h1"),p=head.querySelector("p");if(h)h.textContent="业务数据导出";if(p)p.textContent="用于报表、归档和二次处理；完整系统迁移请使用迁移包"}
 },[view]);
 if(!host)return null;
 if(view==="assets")return createPortal(<UnifiedAssetView/>,host);
 if(view==="backup")return createPortal(<MigrationPanel/>,host);
 return null;
}

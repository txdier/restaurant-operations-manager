"use client";

import {useEffect,useState} from "react";
import {createPortal} from "react-dom";
import {desktopRequest,isDesktop} from "./desktop-api";

type MigrationManifest={appVersion?:string;schemaVersion:number;createdAt?:string;formatVersion:number};
type ActiveView=""|"backup"|"import"|"export";
const errorMessage=(error:unknown)=>error instanceof Error?error.message:String(error);

function detectView():ActiveView{
 const button=document.querySelector(".side nav button.active") as HTMLButtonElement|null;
 const title=button?.getAttribute("title")||button?.textContent||"";
 if(title.includes("备份迁移")||title.includes("备份恢复")||title.includes("备份与恢复")||title.includes("备份与迁移"))return "backup";
 if(title.includes("数据导入")||title.includes("业务数据导入"))return "import";
 if(title.includes("数据导出")||title.includes("业务数据导出"))return "export";
 return "";
}

function renameNavItem(oldLabel:string,newLabel:string){
 const button=Array.from(document.querySelectorAll(".side nav button")).find((item)=>item.getAttribute("title")===oldLabel||item.textContent?.includes(oldLabel)) as HTMLButtonElement|undefined;
 if(!button)return;
 button.title=newLabel;
 for(const node of Array.from(button.childNodes))if(node.nodeType===Node.TEXT_NODE&&node.textContent?.includes(oldLabel))node.textContent=node.textContent.replace(oldLabel,newLabel);
 if(button.classList.contains("active")){
  const headerTitle=document.querySelector("main>header>div:first-child>b");
  if(headerTitle&&headerTitle.textContent===oldLabel)headerTitle.textContent=newLabel;
 }
}

function normalizeNavigation(){
 renameNavItem("装修置物","资产与设备");
 renameNavItem("备份恢复","备份迁移");
}

function normalizeDataCopy(view:ActiveView){
 const content=document.querySelector("section.content");
 if(!content)return;
 const head=content.querySelector(":scope > .head");
 if(view==="import"&&head){
  const h=head.querySelector("h1"),p=head.querySelector("p");
  if(h)h.textContent="业务数据导入";
  if(p)p.textContent="通过 Excel 批量导入快速支出和详细采购；完整系统迁移请到“备份迁移”";
 }
 if(view==="export"&&head){
  const h=head.querySelector("h1"),p=head.querySelector("p");
  if(h)h.textContent="业务数据导出";
  if(p)p.textContent="用于报表、归档和二次处理；完整系统迁移请使用迁移包";
  const scopeLabels=content.querySelectorAll(".scope-options label");
  if(scopeLabels[0]){
   const b=scopeLabels[0].querySelector("b"),small=scopeLabels[0].querySelector("small");
   if(b)b.textContent="全部业务数据";
   if(small)small.textContent="导出系统中保存的全部业务数据，不包含完整恢复所需的数据库结构信息";
  }
  const cards=content.querySelectorAll(".global-options article");
  if(cards[0]){
   const h3=cards[0].querySelector("h3"),p=cards[0].querySelector("p");
   if(h3)h3.textContent="业务数据 Excel";
   if(p)p.textContent="收入、销售、支出、商品、盘点、工资、供应商和设备等业务内容分别保存为工作表。";
  }
  if(cards[1]){
   const h3=cards[1].querySelector("h3"),p=cards[1].querySelector("p");
   if(h3)h3.textContent="业务数据 CSV 压缩包";
   if(p)p.textContent="各类业务数据分别生成 UTF-8 CSV 后打包，适合归档或二次处理，不用于完整系统恢复。";
  }
 }
}

function ensureHost():HTMLElement|null{
 const content=document.querySelector("section.content") as HTMLElement|null;
 if(!content)return null;
 let host=content.querySelector(":scope > .runtime-enhancement-host") as HTMLElement|null;
 if(!host){host=document.createElement("div");host.className="runtime-enhancement-host";content.appendChild(host)}
 const actions=content.querySelector(":scope > .actions");
 if(actions&&actions.nextElementSibling!==host)actions.insertAdjacentElement("afterend",host);
 return host;
}

function MigrationPanel(){
 const [busy,setBusy]=useState(false),[path,setPath]=useState(""),[manifest,setManifest]=useState<MigrationManifest|null>(null),[message,setMessage]=useState("");
 const exportPackage=async()=>{if(!isDesktop())return setMessage("系统迁移仅在 Windows 桌面版中可用");setBusy(true);setMessage("");try{const result=await desktopRequest<{path:string}>("migration/export",{method:"POST",body:"{}"});if(result.path)setMessage(`迁移包已导出：${result.path}`)}catch(error:unknown){setMessage(`导出失败：${errorMessage(error)}`)}finally{setBusy(false)}};
 const choosePackage=async()=>{if(!isDesktop())return setMessage("系统迁移仅在 Windows 桌面版中可用");setBusy(true);setMessage("");try{const selected=await desktopRequest<{path:string}>("migration/select",{method:"POST",body:"{}"});if(!selected.path)return;const checked=await desktopRequest<{manifest:MigrationManifest}>("migration/inspect",{method:"POST",body:JSON.stringify({path:selected.path})});setPath(selected.path);setManifest(checked.manifest);setMessage("迁移包校验通过，可以导入")}catch(error:unknown){setPath("");setManifest(null);setMessage(`检查失败：${errorMessage(error)}`)}finally{setBusy(false)}};
 const importPackage=async()=>{if(!path||!manifest)return;const ok=confirm(`确认导入这个系统迁移包？\n\n来源版本：v${manifest.appVersion||"未知"}\n数据版本：${manifest.schemaVersion}\n生成时间：${manifest.createdAt||"未知"}\n\n当前数据库会先自动生成保护备份，然后再恢复迁移包。`);if(!ok)return;setBusy(true);setMessage("");try{await desktopRequest("migration/import",{method:"POST",body:JSON.stringify({path})});setMessage("系统迁移完成，正在重新载入数据");setTimeout(()=>location.reload(),900)}catch(error:unknown){setMessage(`导入失败：${errorMessage(error)}`)}finally{setBusy(false)}};
 return <div className="panel migration-panel"><div className="pt"><b>系统迁移</b><span>完整数据库迁移，不使用 Excel 还原系统</span></div><div className="migration-body"><div className="migration-guide"><b>旧电脑：导出迁移包</b><span>生成完整 SQLite 数据库和版本校验信息。收入、支出、商品、工资、供应商、系统设置、Logo 等会随数据库一起迁移。</span></div><div className="migration-guide"><b>新电脑：选择并导入迁移包</b><span>导入前检查格式、SHA-256 和数据版本，并自动备份新电脑当前数据库；较旧的数据结构会通过现有 Migration 机制升级。</span></div><div className="migration-buttons"><button className="btn soft" disabled={busy} onClick={exportPackage}>{busy?"处理中…":"导出系统迁移包"}</button><button className="btn soft" disabled={busy} onClick={choosePackage}>{busy?"处理中…":"选择迁移包…"}</button></div>{path&&<div className="migration-selected"><span>已选择</span><b title={path}>{path}</b></div>}{manifest&&<div className="migration-check"><div><span>来源软件版本</span><b>v{manifest.appVersion||"未知"}</b></div><div><span>数据版本</span><b>{manifest.schemaVersion}</b></div><div><span>生成时间</span><b>{manifest.createdAt||"未知"}</b></div><button className="btn" disabled={busy} onClick={importPackage}>导入并完整恢复</button></div>}{message&&<div className={message.includes("失败")?"warn migration-message":"info migration-message"}>{message}</div>}<small className="muted migration-footnote">业务 Excel / CSV 仍用于报表、归档和批量业务录入，不作为完整系统恢复格式。日志和历史备份文件不会打包进迁移包。</small></div></div>
}

export default function RuntimeEnhancements(){
 const [host,setHost]=useState<HTMLElement|null>(null);
 useEffect(()=>{
  const sync=()=>{normalizeNavigation();const next=detectView();normalizeDataCopy(next);setHost(next==="backup"?ensureHost():null)};
  sync();const observer=new MutationObserver(sync);observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:["class"]});const timer=setInterval(sync,700);return()=>{observer.disconnect();clearInterval(timer)};
 },[]);
 if(!host)return null;
 return createPortal(<MigrationPanel/>,host);
}

"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */
import React,{useEffect,useState} from "react";
import {listSuppliersV2,upsertSupplierV2} from "./management-api-v2";

const empty={id:0,name:"",contact:"",phone:"",qualification:"",note:"",active:true};

export default function SuppliersV2({toast}:{toast:(message:string)=>void}){
 const [items,setItems]=useState<any[]>([]),[draft,setDraft]=useState<any>(null),[busy,setBusy]=useState(false);
 const refresh=async()=>{try{const result=await listSuppliersV2();setItems(result.items)}catch(error:any){toast(`读取供应商失败：${error.message}`)}};
 useEffect(()=>{refresh()},[]); // eslint-disable-line react-hooks/exhaustive-deps
 const save=async()=>{if(!draft?.name.trim())return toast("请填写供应商名称");setBusy(true);try{const editing=Boolean(draft.id);await upsertSupplierV2({...draft,name:draft.name.trim()});setDraft(null);await refresh();toast(editing?"供应商已更新":"供应商已新增")}catch(error:any){toast(`保存供应商失败：${error.message}`)}finally{setBusy(false)}};
 const toggle=async(item:any)=>{setBusy(true);try{await upsertSupplierV2({...item,active:!item.active});await refresh();toast(item.active?"供应商已停用":"供应商已启用")}catch(error:any){toast(`更新供应商状态失败：${error.message}`)}finally{setBusy(false)}};
 return <>
  <div className="head"><div><h1>供应管理</h1><p>供应商通讯录与资质记录，不管理欠款和月结</p></div><div><button className="btn" onClick={()=>setDraft({...empty})}>＋ 新增供应商</button></div></div>
  <div className="panel"><table><thead><tr><th>供应商名称</th><th>联系人</th><th>电话</th><th>资质记录</th><th>备注</th><th>状态</th><th>操作</th></tr></thead><tbody>{items.map(item=><tr key={item.id} className={item.active?"":"inactive-product"}><td><b>{item.name}</b></td><td>{item.contact}</td><td>{item.phone}</td><td>{item.qualification}</td><td>{item.note}</td><td><span className={item.active?"yes":"tag"}>{item.active?"启用":"停用"}</span></td><td><button className="link" onClick={()=>setDraft({...item})}>编辑</button><button className="link" disabled={busy} onClick={()=>toggle(item)}>{item.active?"停用":"启用"}</button></td></tr>)}</tbody></table>{!items.length&&<div className="empty-state">暂无供应商，点击右上角新增。</div>}</div>
  {draft&&<div className="shade" onMouseDown={event=>event.currentTarget===event.target&&setDraft(null)}><div className="modal"><div><h2>{draft.id?"编辑供应商":"新增供应商"}</h2><button onClick={()=>setDraft(null)}>×</button></div><label>供应商名称<input autoFocus value={draft.name} onChange={event=>setDraft({...draft,name:event.target.value})}/></label><label>联系人<input value={draft.contact} onChange={event=>setDraft({...draft,contact:event.target.value})}/></label><label>联系电话<input value={draft.phone} onChange={event=>setDraft({...draft,phone:event.target.value})}/></label><label>资质记录<input value={draft.qualification} onChange={event=>setDraft({...draft,qualification:event.target.value})}/></label><label>备注<textarea value={draft.note} onChange={event=>setDraft({...draft,note:event.target.value})}/></label><label><input type="checkbox" checked={draft.active} onChange={event=>setDraft({...draft,active:event.target.checked})}/> 启用供应商</label><footer><button className="btn soft" onClick={()=>setDraft(null)}>取消</button><button className="btn" disabled={busy} onClick={save}>{busy?"正在保存…":"保存"}</button></footer></div></div>}
 </>;
}

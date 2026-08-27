"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */
import React,{useEffect,useState} from "react";
import {createReminderV2,deleteReminderV2,finishReminderV2,listRemindersV2} from "./management-api-v2";

const today=new Date().toISOString().slice(0,10);

export default function RemindersV2({toast}:{toast:(message:string)=>void}){
 const [items,setItems]=useState<any[]>([]),[products,setProducts]=useState<any[]>([]),[summary,setSummary]=useState({overdue:0,future:0,done:0}),[draft,setDraft]=useState<any>(null),[busy,setBusy]=useState(false);
 const refresh=async()=>{try{const result=await listRemindersV2();setItems(result.items);setProducts(result.products);setSummary(result.summary)}catch(error:any){toast(`读取提醒失败：${error.message}`)}};
 useEffect(()=>{refresh()},[]); // eslint-disable-line react-hooks/exhaustive-deps
 const open=()=>setDraft({name:"",productId:products[0]?.id||0,date:today,cycle:0});
 const save=async()=>{if(!draft?.name.trim()||!draft.productId)return toast("请填写提醒名称并选择商品");setBusy(true);try{await createReminderV2({...draft,cycle:Number(draft.cycle||0)});setDraft(null);await refresh();toast("补货提醒已创建")}catch(error:any){toast(`创建提醒失败：${error.message}`)}finally{setBusy(false)}};
 const finish=async(item:any)=>{setBusy(true);try{const result=await finishReminderV2(item.id);await refresh();toast(result.item.done?"提醒已完成":`已完成，下次提醒日期为 ${result.item.date}`)}catch(error:any){toast(`完成提醒失败：${error.message}`)}finally{setBusy(false)}};
 const remove=async(item:any)=>{if(!confirm("删除这条提醒？"))return;setBusy(true);try{await deleteReminderV2(item.id);await refresh();toast("提醒已删除")}catch(error:any){toast(`删除提醒失败：${error.message}`)}finally{setBusy(false)}};
 return <>
  <div className="head"><div><h1>补货提醒</h1><p>根据目测建立提醒，不使用库存数量自动报警</p></div><div><button className="btn" onClick={open}>＋ 新建提醒</button></div></div>
  <div className="summaries"><div><b>{summary.overdue}</b>已逾期</div><div><b>{summary.future}</b>未来提醒</div><div><b>{summary.done}</b>已完成</div></div>
  <div className="panel"><table><thead><tr><th>提醒名称</th><th>商品</th><th>下次提醒日期</th><th>周期</th><th>状态</th><th>操作</th></tr></thead><tbody>{items.map(item=><tr key={item.id}><td><b>{item.name}</b></td><td>{item.product}</td><td>{item.date}</td><td>{item.cycle?`${item.cycle} 天`:"不重复"}</td><td><span className={item.done?"tag":"warn"}>{item.done?"已完成":item.date<today?"已逾期":"待提醒"}</span></td><td><button className="link" disabled={busy||item.done} onClick={()=>finish(item)}>完成</button><button className="danger" disabled={busy} onClick={()=>remove(item)}>删除</button></td></tr>)}</tbody></table>{!items.length&&<div className="empty-state">暂无补货提醒。</div>}</div>
  {draft&&<div className="shade" onMouseDown={event=>event.currentTarget===event.target&&setDraft(null)}><div className="modal"><div><h2>新建补货提醒</h2><button onClick={()=>setDraft(null)}>×</button></div><label>提醒名称<input autoFocus value={draft.name} onChange={event=>setDraft({...draft,name:event.target.value})}/></label><label>商品<select value={draft.productId} onChange={event=>setDraft({...draft,productId:Number(event.target.value)})}><option value={0}>请选择商品</option>{products.map(product=><option key={product.id} value={product.id}>{product.name}（{product.unit}）</option>)}</select></label><label>提醒日期<input type="date" value={draft.date} onChange={event=>setDraft({...draft,date:event.target.value})}/></label><label>重复周期（天，0 为不重复）<input type="number" min="0" value={draft.cycle} onChange={event=>setDraft({...draft,cycle:Math.max(0,Number(event.target.value)||0)})}/></label><footer><button className="btn soft" onClick={()=>setDraft(null)}>取消</button><button className="btn" disabled={busy} onClick={save}>{busy?"正在保存…":"保存"}</button></footer></div></div>}
 </>;
}

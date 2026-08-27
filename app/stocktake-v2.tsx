"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */
import React,{useEffect,useState} from "react";
import {saveStocktakeV2,stocktakeFormV2} from "./management-api-v2";

const today=new Date().toISOString().slice(0,10);

export default function StocktakeV2({toast}:{toast:(message:string)=>void}){
 const [date,setDate]=useState(today),[kind,setKind]=useState("月底盘点"),[rows,setRows]=useState<any[]>([]),[loading,setLoading]=useState(false),[saving,setSaving]=useState(false);
 const load=async()=>{setLoading(true);try{const result=await stocktakeFormV2(date,kind);setRows(result.rows||[])}catch(error:any){toast(`读取盘点数据失败：${error.message}`)}finally{setLoading(false)}};
 useEffect(()=>{load()},[date,kind]); // eslint-disable-line react-hooks/exhaustive-deps
 const update=(productId:number,patch:any)=>setRows(current=>current.map(row=>row.productId===productId?{...row,...patch}:row));
 const save=async()=>{setSaving(true);try{const result=await saveStocktakeV2({date,kind,rows:rows.map(row=>({productId:row.productId,previous:row.previous,actual:Number(row.actual||0),note:row.note||""}))});toast(`已保存 ${result.item.rows.length} 项盘点记录`);await load()}catch(error:any){toast(`保存盘点失败：${error.message}`)}finally{setSaving(false)}};
 return <>
  <div className="head"><div><h1>盘点管理</h1><p>记录每次实际看到的数量；上次盘点数量由数据库按商品历史自动计算</p></div><div><button className="btn" disabled={saving||loading} onClick={save}>{saving?"正在保存…":"保存盘点"}</button></div></div>
  <div className="filters"><label>盘点日期<input type="date" value={date} onChange={event=>setDate(event.target.value)}/></label><label>盘点类型<select value={kind} onChange={event=>setKind(event.target.value)}><option>月底盘点</option><option>临时盘点</option></select></label><span className="info">变化仅供参考，不等同于实际消耗</span></div>
  <div className="panel"><table><thead><tr><th>商品</th><th>上次盘点</th><th>本次实际</th><th>单位</th><th>较上次变化</th><th>备注</th></tr></thead><tbody>{rows.map(row=>{const change=Number(row.actual||0)-Number(row.previous||0);return <tr key={row.productId}><td><b>{row.product}</b><small>{row.brand} {row.spec}</small>{row.active===false&&<small>已停用 · 当前记录保留</small>}</td><td>{row.previous}</td><td><input className="small" type="number" min="0" step="0.001" value={row.actual} onChange={event=>update(row.productId,{actual:Number(event.target.value)})}/></td><td>{row.unit}</td><td><b className={change<0?"down":"up"}>{change>0?"+":""}{change}</b></td><td><input value={row.note||""} onChange={event=>update(row.productId,{note:event.target.value})} placeholder="选填"/></td></tr>})}</tbody></table>{loading&&<div className="empty-state">正在读取盘点商品…</div>}{!loading&&!rows.length&&<div className="empty-state">暂无已启用并参与盘点的商品。</div>}</div>
 </>;
}

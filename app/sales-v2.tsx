"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */
import React,{useEffect,useMemo,useState} from "react";
import {getSalesV2,saveSalesV2} from "./operations-api-v2";

const today=new Date().toISOString().slice(0,10);
const money=(n:number)=>`¥ ${Number(n||0).toLocaleString("zh-CN",{minimumFractionDigits:2,maximumFractionDigits:2})}`;

export default function SalesV2({toast}:{toast:(message:string)=>void}){
 const [saleDate,setSaleDate]=useState(today),[categories,setCategories]=useState<any[]>([]),[existingRows,setExistingRows]=useState<any[]>([]),[vals,setVals]=useState<Record<number,number>>({}),[qty,setQty]=useState<Record<number,number>>({}),[dailyIncome,setDailyIncome]=useState(0),[loading,setLoading]=useState(false),[saving,setSaving]=useState(false);
 const load=async(date:string)=>{setLoading(true);try{const result=await getSalesV2(date);setCategories(result.categories||[]);setExistingRows(result.rows||[]);setDailyIncome(Number(result.dailyIncome||0));setVals(Object.fromEntries((result.rows||[]).map((row:any)=>[Number(row.categoryId||0),Number(row.amount||0)])));setQty(Object.fromEntries((result.rows||[]).map((row:any)=>[Number(row.categoryId||0),Number(row.qty||0)])))}catch(error:any){toast(`读取销售统计失败：${error.message}`)}finally{setLoading(false)}};
 useEffect(()=>{load(saleDate)},[saleDate]); // eslint-disable-line react-hooks/exhaustive-deps
 const existingIds=useMemo(()=>new Set(existingRows.map(row=>Number(row.categoryId||0))),[existingRows]);
 const visible=useMemo(()=>categories.filter(category=>category.active||existingIds.has(Number(category.id))),[categories,existingIds]);
 const sale=useMemo(()=>visible.reduce((sum,category)=>sum+Number(vals[category.id]||0),0),[visible,vals]);
 const quantity=useMemo(()=>visible.reduce((sum,category)=>sum+Number(qty[category.id]||0),0),[visible,qty]);
 const save=async()=>{setSaving(true);try{await saveSalesV2(saleDate,visible.map(category=>({categoryId:category.id,category:category.name,qty:Number(qty[category.id]||0),amount:Number(vals[category.id]||0)})));toast(`已保存 ${visible.length} 个销售分类`);await load(saleDate)}catch(error:any){toast(`保存销售统计失败：${error.message}`)}finally{setSaving(false)}};
 return <>
  <div className="head"><div><h1>销售统计录入</h1><p>按收银小票上的销售大类汇总录入；当天收入校验实时读取 SQLite</p></div><div><button className="btn" disabled={saving||loading} onClick={save}>{saving?"正在保存…":"保存统计"}</button></div></div>
  <div className="filters"><label>销售日期<input type="date" value={saleDate} onChange={event=>setSaleDate(event.target.value)}/></label><span className="warn">收入校验：与当日收入相差 {money(Math.abs(dailyIncome-sale))}</span><span className="info">周期收入不参与单日销售校验</span></div>
  <div className="panel"><table className="dense"><thead><tr><th>分类名称</th><th>销售数量</th><th>销售金额</th><th>销售收入</th></tr></thead><tbody>{visible.map(category=><tr key={category.id} className={category.active?"":"inactive-product"}><td><b>{category.name}</b>{!category.active&&<small>已停用 · 保留历史录入</small>}</td><td><input type="number" min="0" step="0.01" value={qty[category.id]||0} onChange={event=>setQty({...qty,[category.id]:Math.max(0,Number(event.target.value)||0)})}/></td><td>{money(vals[category.id]||0)}</td><td><input type="number" min="0" step="0.01" value={vals[category.id]||0} onChange={event=>setVals({...vals,[category.id]:Math.max(0,Number(event.target.value)||0)})}/></td></tr>)}</tbody><tfoot><tr><td>合计</td><td>{quantity.toLocaleString("zh-CN")}</td><td>{money(sale)}</td><td>{money(sale)}</td></tr></tfoot></table>{loading&&<div className="empty-state">正在读取销售数据…</div>}{!loading&&!visible.length&&<div className="empty-state">暂无启用的销售分类，请先到系统设置中启用。</div>}</div>
 </>;
}

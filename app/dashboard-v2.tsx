"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */
import React,{useEffect,useMemo,useState} from "react";
import {dashboardDetailV2} from "./operations-api-v2";

const today=new Date().toISOString().slice(0,10);
const money=(n:number)=>`¥ ${Number(n||0).toLocaleString("zh-CN",{minimumFractionDigits:2,maximumFractionDigits:2})}`;

export default function DashboardV2({go,toast}:{go:(key:any)=>void;toast:(message:string)=>void}){
 const [data,setData]=useState<any>({todayIncome:0,todayExpense:0,monthIncome:0,monthExpense:0,monthBalance:0,pendingReminders:0,trend:[],categories:[]}),[loading,setLoading]=useState(true);
 useEffect(()=>{setLoading(true);dashboardDetailV2(today).then(setData).catch((error:any)=>toast(`加载经营概览失败：${error.message}`)).finally(()=>setLoading(false))},[]); // eslint-disable-line react-hooks/exhaustive-deps
 const max=useMemo(()=>Math.max(1,...(data.trend||[]).flatMap((row:any)=>[Number(row.income||0),Number(row.expense||0)])),[data.trend]);
 return <>
  <div className="head"><div><h1>经营概览</h1><p>今天和本月的经营情况直接由 SQLite 汇总</p></div><div><button className="btn soft" onClick={()=>go("expenses")}>＋ 记一笔支出</button><button className="btn" onClick={()=>go("income")}>＋ 录入收入</button></div></div>
  <div className="kpis">{[["今日营业额",data.todayIncome,"￥","green"],["今日支出",data.todayExpense,"支","orange"],["本月营业额",data.monthIncome,"月","blue"],["本月支出",data.monthExpense,"票","purple"]].map((item:any)=><article key={item[0]}><i className={item[3]}>{item[2]}</i><div><span>{item[0]}</span><strong>{loading?"—":money(item[1])}</strong></div></article>)}</div>
  <div className="middle"><article><span>本月收支差额 <em>非利润</em></span><strong>{loading?"—":money(data.monthBalance)}</strong><small>按已录入的有效收入和支出自动计算</small></article><article className="todo"><i>♧<b>{data.pendingReminders||0}</b></i><div><strong>待办提醒</strong><p>{data.pendingReminders?`${data.pendingReminders} 项补货提醒尚未完成`:"当前没有待办提醒"}</p></div><button onClick={()=>go("reminders")}>查看全部 ›</button></article></div>
  <div className="charts"><article className="panel"><div className="pt"><b>最近 7 天经营概览</b><span>收入 / 支出</span></div><div className="bars">{(data.trend||[]).map((row:any)=><div key={row.date}><i title={`收入 ${money(row.income)}`} style={{height:`${Math.max(2,Number(row.income||0)/max*100)}%`}}/><i title={`支出 ${money(row.expense)}`} style={{height:`${Math.max(2,Number(row.expense||0)/max*100)}%`}}/><span>{String(row.date).slice(5)}</span></div>)}</div>{!loading&&!data.trend?.length&&<div className="empty-state">最近7天暂无经营数据。</div>}</article><article className="panel"><div className="pt"><b>支出分类</b><span>本月有效支出</span></div><div className="simple-summary">{(data.categories||[]).map((row:any)=><p key={row.name}><span>{row.name||"未分类"}</span><b>{money(row.amount)}</b></p>)}{!loading&&!data.categories?.length&&<p className="muted">本月暂无支出</p>}</div></article></div>
 </>;
}

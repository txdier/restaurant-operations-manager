"use client";
import React,{useEffect,useMemo,useState} from "react";
import {listIncomeV2,upsertIncomeV2} from "./data-api-v2";

const today=new Date().toISOString().slice(0,10);
const money=(n:number)=>`¥ ${Number(n||0).toLocaleString("zh-CN",{minimumFractionDigits:2,maximumFractionDigits:2})}`;
type Mode="day"|"period";
type RecordRow={id?:number;date:string;entryMode:Mode;periodStart:string;periodEnd:string;dineIn:number;chess:number;delivery:number;note:string};
const blank=(mode:Mode,date=today):RecordRow=>({date,entryMode:mode,periodStart:date,periodEnd:date,dineIn:0,chess:0,delivery:0,note:""});

export default function IncomeV2({toast}:{toast:(message:string)=>void}){
 const [record,setRecord]=useState<RecordRow>(()=>blank("day"));
 const [loading,setLoading]=useState(false),[saving,setSaving]=useState(false);
 const total=useMemo(()=>Number(record.dineIn||0)+Number(record.chess||0)+Number(record.delivery||0),[record]);

 const load=async(next:RecordRow)=>{
  setLoading(true);
  try{
   const queryDate=next.entryMode==="day"?next.date:next.periodEnd;
   const result=await listIncomeV2(queryDate,queryDate,200);
   const found=result.items.find((item:any)=>next.entryMode==="day"
     ? item.entryMode==="day"&&item.date===next.date
     : item.entryMode==="period"&&item.periodStart===next.periodStart&&item.periodEnd===next.periodEnd);
   setRecord(found?{...blank(next.entryMode,queryDate),...found}:next);
  }catch(error:any){toast(`读取收入失败：${error.message}`);setRecord(next)}finally{setLoading(false)}
 };

 useEffect(()=>{load(record)},[]); // eslint-disable-line react-hooks/exhaustive-deps
 const changeMode=(mode:Mode)=>load(blank(mode));
 const selectDay=(date:string)=>load(blank("day",date));
 const selectPeriod=(periodStart:string,periodEnd:string)=>load({...blank("period",periodEnd),periodStart,periodEnd});
 const save=async()=>{
  if(record.entryMode==="period"&&record.periodStart>record.periodEnd)return toast("周期开始日期不能晚于结束日期");
  setSaving(true);
  try{
   const payload={...record,date:record.entryMode==="period"?record.periodEnd:record.date,periodStart:record.entryMode==="period"?record.periodStart:record.date,periodEnd:record.entryMode==="period"?record.periodEnd:record.date};
   const result=await upsertIncomeV2(payload);setRecord(result.item);toast(`已保存${result.item.entryMode==="day"?result.item.date:`${result.item.periodStart} 至 ${result.item.periodEnd}`}收入`);
  }catch(error:any){toast(`保存收入失败：${error.message}`)}finally{setSaving(false)}
 };
 const setAmount=(key:"dineIn"|"chess"|"delivery",value:string)=>setRecord(current=>({...current,[key]:Math.max(0,Number(value)||0)}));
 return <>
  <div className="head"><div><h1>收入录入</h1><p>按日或经营周期录入收入，金额直接写入关系数据库</p></div></div>
  <div className="tabs"><button className={record.entryMode==="day"?"on":""} onClick={()=>changeMode("day")}>按日录入</button><button className={record.entryMode==="period"?"on":""} onClick={()=>changeMode("period")}>按周期录入</button></div>
  <div className="panel form income-form">
   <div className="filters income-date-bar">{record.entryMode==="day"?<label>营业日期<input type="date" value={record.date} onChange={event=>selectDay(event.target.value)}/></label>:<><label>周期开始<input type="date" value={record.periodStart} onChange={event=>selectPeriod(event.target.value,record.periodEnd)}/></label><label>周期结束<input type="date" value={record.periodEnd} onChange={event=>selectPeriod(record.periodStart,event.target.value)}/></label></>}<span className="info">{loading?"正在读取已有记录…":record.id?"已读取已有记录，保存将更新":"当前日期/周期尚未录入"}</span></div>
   <table><thead><tr><th>收入来源</th><th>金额（元）</th><th>说明</th></tr></thead><tbody>
    <tr><td><b>堂食</b></td><td><div className="cash">¥<input type="number" min="0" step="0.01" value={record.dineIn} onChange={event=>setAmount("dineIn",event.target.value)}/></div></td><td className="muted">{record.entryMode==="day"?"按当天实际收入填写":"填写整个周期的汇总金额"}</td></tr>
    <tr><td><b>棋牌房</b></td><td><div className="cash">¥<input type="number" min="0" step="0.01" value={record.chess} onChange={event=>setAmount("chess",event.target.value)}/></div></td><td className="muted">按实际收入填写</td></tr>
    <tr><td><b>外送</b></td><td><div className="cash">¥<input type="number" min="0" step="0.01" value={record.delivery} onChange={event=>setAmount("delivery",event.target.value)}/></div></td><td className="muted">按实际收入填写</td></tr>
    <tr className="sum"><td>合计</td><td>{money(total)}</td><td>自动计算</td></tr>
   </tbody></table>
   <label className="block income-note">备注<textarea value={record.note} onChange={event=>setRecord({...record,note:event.target.value})} placeholder="请输入备注（可选）"/></label>
   {record.entryMode==="period"&&<div className="snapshot-notice"><b>统计归属</b><span>周期收入按周期结束日归属统计，整笔计入且不会按天拆分。</span></div>}
   <div className="income-save-bar"><span>确认日期和金额无误后保存，本次合计 <b>{money(total)}</b></span><button className="btn" disabled={saving||loading} onClick={save}>{saving?"正在保存…":"保存收入"}</button></div>
  </div>
 </>;
}

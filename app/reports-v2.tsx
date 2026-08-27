"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */
import React,{useEffect,useMemo,useState} from "react";
import {reportExpensesV2,reportIncomeV2,reportOptionsV2,reportPricesV2,reportSalesV2,reportStockV2,reportSummaryV2} from "./data-api-v2";
import {exportReportV2} from "./report-export-api-v2";

type Tab="income"|"expense"|"sales"|"stock"|"price";
type Column={key:string;label:string;money?:boolean;render?:(row:any)=>React.ReactNode;className?:(row:any)=>string};
const today=new Date().toISOString().slice(0,10);
const money=(n:number)=>`¥ ${Number(n||0).toLocaleString("zh-CN",{minimumFractionDigits:2,maximumFractionDigits:2})}`;

const COLUMNS:Record<Tab,Column[]>={
 expense:[
  {key:"date",label:"日期"},{key:"mode",label:"方式",render:r=><span className="tag">{r.mode}</span>},{key:"category",label:"类别"},{key:"item",label:"项目"},{key:"amount",label:"金额",money:true},{key:"handler",label:"经手人"},{key:"status",label:"状态"}
 ],
 income:[
  {key:"date",label:"记账日期"},{key:"entryMode",label:"录入方式",render:r=><span className="tag">{r.entryMode==="period"?"按周期":"按日"}</span>},{key:"period",label:"经营周期",render:r=>r.entryMode==="period"?`${r.periodStart} 至 ${r.periodEnd}`:r.date},{key:"dineIn",label:"堂食",money:true},{key:"chess",label:"棋牌房",money:true},{key:"delivery",label:"外送",money:true},{key:"total",label:"合计",money:true}
 ],
 sales:[{key:"date",label:"日期"},{key:"category",label:"分类"},{key:"qty",label:"数量"},{key:"amount",label:"金额",money:true}],
 stock:[
  {key:"date",label:"日期"},{key:"kind",label:"类型"},{key:"product",label:"商品"},{key:"previous",label:"上次"},{key:"actual",label:"本次"},{key:"unit",label:"单位"},{key:"change",label:"变化",render:r=>`${Number(r.change)>0?"+":""}${r.change}`,className:r=>Number(r.change)<0?"down":"up"},{key:"note",label:"备注"}
 ],
 price:[{key:"date",label:"日期"},{key:"qty",label:"数量"},{key:"unit",label:"单位"},{key:"price",label:"单价",money:true},{key:"amount",label:"小计",money:true},{key:"handler",label:"经手人"}],
};

function Tabs({value,setValue}:{value:Tab;setValue:(value:Tab)=>void}){
 const items:[Tab,string][]=[["income","收入明细"],["expense","支出查询"],["sales","销售统计"],["stock","盘点记录"],["price","商品历史价格"]];
 return <div className="tabs">{items.map(([key,label])=><button key={key} className={value===key?"on":""} onClick={()=>setValue(key)}>{label}</button>)}</div>;
}

export default function ReportsV2({toast}:{toast:(value:string)=>void}){
 const [tab,setTab]=useState<Tab>(()=>typeof window!=="undefined"&&sessionStorage.getItem("report-open-price")==="1"?"price":"expense");
 const [start,setStart]=useState(today.slice(0,7)+"-01"),[end,setEnd]=useState(today),[keyword,setKeyword]=useState("");
 const [category,setCategory]=useState("全部类别"),[handler,setHandler]=useState("全部经手人"),[status,setStatus]=useState("有效"),[productId,setProductId]=useState(0);
 const [options,setOptions]=useState<{categories:string[];handlers:string[];products:any[]}>({categories:[],handlers:[],products:[]});
 const [summary,setSummary]=useState({income:0,expense:0,balance:0});
 const [rows,setRows]=useState<any[]>([]),[total,setTotal]=useState(0),[totalPages,setTotalPages]=useState(1),[page,setPage]=useState(1),[pageSize,setPageSize]=useState(20);
 const [sortBy,setSortBy]=useState("date"),[sortOrder,setSortOrder]=useState<"asc"|"desc">("desc"),[loading,setLoading]=useState(false),[exporting,setExporting]=useState(false);
 const [priceInfo,setPriceInfo]=useState<any>(null),[priceSummary,setPriceSummary]=useState({min:0,max:0,latest:0,average:0});

 useEffect(()=>{sessionStorage.removeItem("report-open-price");reportOptionsV2().then(result=>{setOptions(result);const remembered=Number(sessionStorage.getItem("report-product-id")||0);setProductId(remembered||Number(result.products[0]?.id||0))}).catch(error=>toast(`加载查询选项失败：${error.message}`))},[]);
 useEffect(()=>{if(start>end)return;reportSummaryV2(start,end).then(setSummary).catch(error=>toast(`加载汇总失败：${error.message}`))},[start,end]);
 useEffect(()=>{setPage(1);setSortBy("date");setSortOrder("desc")},[tab]);
 useEffect(()=>{setPage(1)},[start,end,keyword,category,handler,status,productId,pageSize]);

 useEffect(()=>{
  if(start>end){setRows([]);setTotal(0);setTotalPages(1);return}
  const timer=setTimeout(async()=>{
   setLoading(true);
   try{
    const common={start,end,keyword,sortBy,sortOrder,page,pageSize};
    let result:any;
    if(tab==="expense")result=await reportExpensesV2({...common,category,handler,status});
    else if(tab==="income")result=await reportIncomeV2(common);
    else if(tab==="sales")result=await reportSalesV2(common);
    else if(tab==="stock")result=await reportStockV2(common);
    else if(productId)result=await reportPricesV2(productId,{...common,keyword:""});
    else result={items:[],total:0,totalPages:1,product:null,summary:{min:0,max:0,latest:0,average:0}};
    setRows(result.items||[]);setTotal(Number(result.total||0));setTotalPages(Math.max(1,Number(result.totalPages||1)));
    if(tab==="price"){setPriceInfo(result.product||null);setPriceSummary(result.summary||{min:0,max:0,latest:0,average:0})}
   }catch(error:any){toast(`查询失败：${error.message}`)}finally{setLoading(false)}
  },220);
  return()=>clearTimeout(timer);
 },[tab,start,end,keyword,category,handler,status,productId,page,pageSize,sortBy,sortOrder]);

 useEffect(()=>{if(page>totalPages)setPage(totalPages)},[page,totalPages]);
 const columns=COLUMNS[tab],from=total?(page-1)*pageSize+1:0,to=Math.min(page*pageSize,total);
 const sort=(key:string)=>{if(key==="period")return;setPage(1);if(sortBy===key)setSortOrder(current=>current==="asc"?"desc":"asc");else{setSortBy(key);setSortOrder("asc")}};
 const keywordPlaceholder=tab==="expense"?"项目、类别、方式或经手人":tab==="income"?"日期、录入方式或备注":tab==="sales"?"日期或销售分类":"日期、类型、商品或备注";
 const exportCurrent=async()=>{setExporting(true);try{const result=await exportReportV2(tab,{start,end,keyword,category,handler,status,productId,sortBy,sortOrder});if(result.path)toast(`已导出：${result.path}`)}catch(error:any){toast(`导出失败：${error.message}`)}finally{setExporting(false)}};
 const value=(row:any,column:Column)=>column.render?column.render(row):column.money?money(Number(row[column.key]||0)):String(row[column.key]??"");
 const title=tab==="expense"?"支出查询结果":tab==="income"?"收入明细":tab==="sales"?"销售分类明细":tab==="stock"?"盘点记录":`商品历史价格 · ${priceInfo?.name||"暂无商品"}`;

 return <>
  <div className="head"><div><h1>查询统计</h1><p>收入、支出、销售、盘点和价格历史统一查询；桌面版由 SQLite 直接筛选、排序和分页</p></div><div><button className="btn soft" disabled={exporting||loading} onClick={exportCurrent}>{exporting?"正在导出…":"⇩ 导出查询结果"}</button></div></div>
  <Tabs value={tab} setValue={setTab}/>
  <div className="filters report-filters">
   <label>开始日期<input type="date" value={start} onChange={event=>setStart(event.target.value)}/></label>
   <label>结束日期<input type="date" value={end} onChange={event=>setEnd(event.target.value)}/></label>
   {tab==="expense"&&<><label>支出类别<select value={category} onChange={event=>setCategory(event.target.value)}><option>全部类别</option>{options.categories.map(name=><option key={name}>{name}</option>)}</select></label><label>经手人<select value={handler} onChange={event=>setHandler(event.target.value)}><option>全部经手人</option>{options.handlers.map(name=><option key={name}>{name}</option>)}</select></label><label>状态<select value={status} onChange={event=>setStatus(event.target.value)}><option>有效</option><option>已作废</option><option>全部</option></select></label></>}
   {tab==="price"?<label>商品<select value={productId} onChange={event=>setProductId(Number(event.target.value))}>{options.products.map(product=><option value={product.id} key={product.id}>{product.name}（{product.unit}{product.active?"":"，已停用"}）</option>)}</select></label>:<label className="keyword">关键字<div className="search">⌕<input value={keyword} onChange={event=>setKeyword(event.target.value)} placeholder={keywordPlaceholder}/></div></label>}
  </div>
  {start>end&&<p className="warn">开始日期不能晚于结束日期。</p>}
  {tab==="income"&&<p className="filter-help">周期收入按周期结束日归属当前查询范围，整笔计入且不会按天分摊。</p>}
  <div className="report"><div><span>期间营业额</span><b>{money(summary.income)}</b></div><div><span>期间有效支出</span><b>{money(summary.expense)}</b></div><div><span>收支差额</span><b>{money(summary.balance)}</b></div><div><span>当前结果</span><b>{total} 条</b></div></div>
  {tab==="price"&&priceInfo&&<div className="price-summary"><span>最低价 <b>{money(priceSummary.min)}/{priceInfo.unit}</b></span><span>最高价 <b>{money(priceSummary.max)}/{priceInfo.unit}</b></span><span>最近价格 <b>{money(priceSummary.latest)}/{priceInfo.unit}</b></span><span>平均价格 <b>{money(priceSummary.average)}/{priceInfo.unit}</b></span></div>}
  <article className="panel"><div className="pt"><b>{title}</b><span>{loading?"正在查询…":`${total} 条 · 服务端分页排序`}</span></div>
   <table className="report-table"><thead><tr>{columns.map(column=><th key={column.key} aria-sort={sortBy===column.key?(sortOrder==="asc"?"ascending":"descending"):"none"}><button className={sortBy===column.key?"sort-button active":"sort-button"} disabled={column.key==="period"} onClick={()=>sort(column.key)}>{column.label}<span aria-hidden="true">{column.key==="period"?"":sortBy===column.key?(sortOrder==="asc"?"↑":"↓"):"↕"}</span></button></th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={row.id??`${page}-${index}`} className={tab==="expense"&&row.status!=="有效"?"void":""}>{columns.map(column=><td key={column.key} className={column.className?.(row)||""}>{value(row,column)}</td>)}</tr>)}</tbody></table>
   {!loading&&!rows.length&&<div className="empty-state report-empty">当前条件下没有查询结果</div>}
   <div className="report-pagination"><span>显示第 {from}–{to} 条，共 {total} 条</span><div><label>每页<select value={pageSize} onChange={event=>setPageSize(Number(event.target.value))}><option value={20}>20 条</option><option value={50}>50 条</option><option value={100}>100 条</option></select></label><button disabled={page<=1||loading} onClick={()=>setPage(1)}>首页</button><button disabled={page<=1||loading} onClick={()=>setPage(current=>Math.max(1,current-1))}>上一页</button><b>第 {page} / {totalPages} 页</b><button disabled={page>=totalPages||loading} onClick={()=>setPage(current=>Math.min(totalPages,current+1))}>下一页</button><button disabled={page>=totalPages||loading} onClick={()=>setPage(totalPages)}>末页</button></div></div>
  </article>
 </>;
}

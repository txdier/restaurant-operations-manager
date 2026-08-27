"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */
import React,{useState} from "react";
import {applyImportV2,exportAllV2,previewImportV2,saveImportTemplateV2,selectImportFileV2} from "./data-api-v2";

const today=new Date().toISOString().slice(0,10);
const money=(n:number)=>`¥ ${Number(n||0).toLocaleString("zh-CN",{minimumFractionDigits:2,maximumFractionDigits:2})}`;

export default function DataExchangeV2({toast}:{toast:(message:string)=>void}){
 const [tab,setTab]=useState<"import"|"export">("import");
 return <>
  <div className="head"><div><h1>数据交换</h1><p>集中进行业务数据导入和导出；桌面版直接读写关系数据库</p></div></div>
  <div className="tabs"><button className={tab==="import"?"on":""} onClick={()=>setTab("import")}>数据导入</button><button className={tab==="export"?"on":""} onClick={()=>setTab("export")}>数据导出</button></div>
  {tab==="import"?<ImportV2 toast={toast}/>:<ExportV2 toast={toast}/>} 
 </>;
}

function ImportV2({toast}:{toast:(message:string)=>void}){
 const [path,setPath]=useState("");
 const [preview,setPreview]=useState<any>(null);
 const [operation,setOperation]=useState<""|"template"|"choose"|"preview"|"apply">("");
 const [createUnknown,setCreateUnknown]=useState(true),[importDuplicates,setImportDuplicates]=useState(false),[showDuplicates,setShowDuplicates]=useState(false);
 const busy=operation!=="",duplicateCount=Number(preview?.counts?.duplicateQuickExpenses||0),quickImportCount=Number(preview?.counts?.quickExpenses||0)+(importDuplicates?duplicateCount:0);

 const template=async()=>{setOperation("template");try{const result=await saveImportTemplateV2();if(result.path)toast(`模板已保存：${result.path}`)}catch(error:any){toast(`保存模板失败：${error.message}`)}finally{setOperation("")}};
 const choose=async()=>{setOperation("choose");try{const result=await selectImportFileV2();if(result.path){setPath(result.path);setPreview(null);setImportDuplicates(false);setShowDuplicates(false)}}catch(error:any){toast(`选择文件失败：${error.message}`)}finally{setOperation("")}};
 const inspect=async()=>{if(!path)return toast("请先选择 Excel 文件");setOperation("preview");try{const result=await previewImportV2(path);setPreview(result.preview);setImportDuplicates(false);setShowDuplicates(false);toast(result.preview.errors.length?`发现 ${result.preview.errors.length} 个问题`:`预览完成，共 ${result.preview.counts.quickExpenses+result.preview.counts.purchaseLines} 条可导入明细`)}catch(error:any){toast(`预览失败：${error.message}`)}finally{setOperation("")}};
 const apply=async()=>{
  if(!preview||preview.errors.length)return toast("请先完成无错误的导入预览");
  if(!confirm(`确认导入 ${quickImportCount} 笔快速支出和 ${preview.counts.purchaseLines} 条采购明细？${duplicateCount&&!importDuplicates?`\n将跳过 ${duplicateCount} 笔重复快速支出。`:""}\n导入前会自动备份。`))return;
  setOperation("apply");
  try{await applyImportV2(path,createUnknown,importDuplicates);toast("导入成功，正在刷新数据");setTimeout(()=>location.reload(),700)}catch(error:any){toast(`导入失败：${error.message}`)}finally{setOperation("")}
 };

 return <>
  <div className="exchange-subhead"><div><b>Excel 批量导入</b><span>导入快速支出和详细采购；预览和重复检查直接查询 SQLite</span></div><button className="btn soft" disabled={busy} onClick={template}>{operation==="template"?"等待保存位置…":"保存填写模板"}</button></div>
  <div className="panel form import-panel">
   <div className="snapshot-notice"><b>金额继续按元填写</b><span>Excel 中仍按元填写金额和单价，写入数据库时统一转换为整数分；详细采购按采购单号防止重复导入。</span></div>
   <div className="import-file-row"><label>Excel 文件<input readOnly value={path} title={path} placeholder="尚未选择 .xlsx 文件"/></label><button className="btn soft" disabled={busy} onClick={choose}>{operation==="choose"?"等待选择…":"选择文件…"}</button><button className="btn" disabled={busy} onClick={inspect}>{operation==="preview"?"正在检查…":"检查并预览"}</button></div>
   <small className="muted">预览只查询本次 Excel 涉及的分类、商品、采购单号和重复候选，不再加载全部历史支出。</small>
  </div>
  {preview&&<>
   <div className="report"><div><span>可导入快速支出</span><b>{preview.counts.quickExpenses} 笔</b></div><div><span>重复快速支出</span><b>{duplicateCount} 笔</b></div><div><span>采购单</span><b>{preview.counts.purchaseOrders} 张</b></div><div><span>采购明细</span><b>{preview.counts.purchaseLines} 条</b></div></div>
   <article className="panel"><div className="pt"><b>导入检查结果</b><span>{preview.errors.length?"需要修正":duplicateCount?"发现重复，默认跳过":"可以导入"}</span></div><div className="form">
    {preview.errors.map((item:string,index:number)=><p className="warn" key={`e-${index}`}>{item}</p>)}
    {preview.warnings.map((item:string,index:number)=><p className="info" key={`w-${index}`}>{item}</p>)}
    {!preview.errors.length&&!preview.warnings.length&&<p className="ok">文件检查通过，没有发现问题。</p>}
    {duplicateCount>0&&<div className="duplicate-imports"><button type="button" className="duplicate-import-summary" aria-expanded={showDuplicates} onClick={()=>setShowDuplicates(value=>!value)}><span><b>重复快速支出明细</b><small>{importDuplicates?`已选择仍然导入 ${duplicateCount} 笔重复支出`:`共 ${duplicateCount} 笔，默认全部跳过`}</small></span><strong>{showDuplicates?"收起明细 ↑":"展开明细 ↓"}</strong></button>{showDuplicates&&<div className="duplicate-import-details"><div className="duplicate-import-table"><table className="dense"><thead><tr><th>Excel 行</th><th>日期</th><th>类别</th><th>金额</th><th>经手人</th><th>备注</th><th>原因</th></tr></thead><tbody>{preview.duplicateQuickExpenses.map((row:any)=><tr key={row.row}><td>{row.row}</td><td>{row.date}</td><td>{row.category}</td><td>{money(row.amount)}</td><td>{row.handler||"—"}</td><td>{row.note||"—"}</td><td><span className="warn">{row.reason}</span></td></tr>)}</tbody></table></div><label className="duplicate-import-option"><input type="checkbox" checked={importDuplicates} onChange={event=>setImportDuplicates(event.target.checked)}/><span><b>仍然导入这 {duplicateCount} 笔重复支出</b><small>默认不导入；仅在确认它们是不同业务时勾选。</small></span></label></div>}</div>}
    {preview.unknownProducts.length>0&&<label className="block"><span><input type="checkbox" checked={createUnknown} onChange={event=>setCreateUnknown(event.target.checked)}/> 自动新增商品：{preview.unknownProducts.map((product:any)=>`${product.name}（${product.unit}）`).join("、")}</span></label>}
    <div className="tablefoot"><span>类别、商品单位或采购单号错误会阻止导入。</span><button className="btn" disabled={busy} onClick={apply}>{operation==="apply"?"正在导入…":`确认导入 ${quickImportCount+preview.counts.purchaseLines} 条`}</button></div>
   </div></article>
  </>}
 </>;
}

function ExportV2({toast}:{toast:(message:string)=>void}){
 const [scope,setScope]=useState<"all"|"range">("all"),[start,setStart]=useState(today.slice(0,4)+"-01-01"),[end,setEnd]=useState(today),[busy,setBusy]=useState(false);
 const run=async(format:"xlsx"|"zip")=>{
  if(scope==="range"&&start>end)return toast("开始日期不能晚于结束日期");
  setBusy(true);
  try{const result=await exportAllV2(format,scope==="range"?start:"",scope==="range"?end:"");if(result.path)toast(`已导出：${result.path}`)}catch(error:any){toast(`导出失败：${error.message}`)}finally{setBusy(false)}
 };
 return <>
  <div className="exchange-subhead"><div><b>经营数据导出</b><span>关系表逐批读取并直接生成文件，不再先构造完整前端数据集</span></div></div>
  <div className="panel global-export"><div className="pt"><b>导出范围</b><span>查询结果请在“查询统计”页面直接导出</span></div><div className="scope-options"><label><input type="radio" name="scope-v2" checked={scope==="all"} onChange={()=>setScope("all")}/><span><b>全部数据</b><small>导出系统中保存的全部经营数据</small></span></label><label><input type="radio" name="scope-v2" checked={scope==="range"} onChange={()=>setScope("range")}/><span><b>指定时间范围</b><small>仅导出该日期范围内的业务数据</small></span></label></div>{scope==="range"&&<div className="range-fields"><label>开始日期<input type="date" value={start} onChange={event=>setStart(event.target.value)}/></label><span>至</span><label>结束日期<input type="date" value={end} onChange={event=>setEnd(event.target.value)}/></label></div>}</div>
  <div className="options global-options"><article><i>X</i><div><h3>全局数据 Excel</h3><p>使用 write-only 工作簿逐行输出收入、销售、支出、商品、盘点、工资、供应商和设备数据。</p><button className="btn soft" disabled={busy} onClick={()=>run("xlsx")}>{busy?"正在生成…":"导出 Excel"}</button></div></article><article><i>ZIP</i><div><h3>全局 CSV 压缩包</h3><p>各数据表逐行写入 UTF-8 CSV 后打包，适合归档、迁移和二次处理。</p><button className="btn soft" disabled={busy} onClick={()=>run("zip")}>{busy?"正在生成…":"导出 CSV 压缩包"}</button></div></article></div>
 </>;
}

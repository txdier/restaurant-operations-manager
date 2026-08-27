"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */
import React,{useEffect,useState} from "react";
import {listProductsV2,productHistoryStatusV2,replaceProductUnitV2,setProductActiveV2,upsertProductV2} from "./data-api-v2";

type Product={id:number;name:string;category:string;brand:string;spec:string;unit:string;stocktake:boolean;reminder:boolean;active:boolean;createdAt?:string};
const blank:Product={id:0,name:"",category:"食材",brand:"",spec:"",unit:"kg",stocktake:true,reminder:false,active:true};
const categories=["食材","调料","食用油","米面粮油","酒水","餐具类","日化类","纸品类","其他"];
const units=["kg","斤","箱","包","个","瓶","桶","袋","盒"];

export default function ProductsV2({toast,go}:{toast:(message:string)=>void;go:(key:any)=>void}){
 const [q,setQ]=useState(""),[items,setItems]=useState<Product[]>([]),[loading,setLoading]=useState(false),[busy,setBusy]=useState(false);
 const [dialog,setDialog]=useState<"new"|"edit"|null>(null),[draft,setDraft]=useState<Product>(blank),[original,setOriginal]=useState<Product|null>(null);
 const [unitWarning,setUnitWarning]=useState<{original:Product;draft:Product}|null>(null);
 const refresh=async(search=q)=>{setLoading(true);try{const result=await listProductsV2(search,undefined,1000);setItems(result.items)}catch(error:any){toast(`读取商品失败：${error.message}`)}finally{setLoading(false)}};
 useEffect(()=>{const timer=setTimeout(()=>refresh(q),160);return()=>clearTimeout(timer)},[q]); // eslint-disable-line react-hooks/exhaustive-deps
 const openNew=()=>{setOriginal(null);setDraft({...blank});setDialog("new")};
 const openEdit=(product:Product)=>{setOriginal(product);setDraft({...product});setDialog("edit")};
 const close=()=>{setDialog(null);setOriginal(null);setUnitWarning(null)};
 const save=async()=>{
  if(!draft.name.trim()||!draft.unit.trim())return toast("请填写商品名称和计量单位");
  setBusy(true);
  try{
   if(dialog==="edit"&&original&&original.unit!==draft.unit){
    const history=await productHistoryStatusV2(original.id);
    if(history.hasHistory){setUnitWarning({original,draft:{...draft}});setBusy(false);return}
   }
   await upsertProductV2({...draft,name:draft.name.trim()});close();await refresh();toast(dialog==="new"?"商品已新增":"商品档案已更新；历史采购与统计未改变");
  }catch(error:any){toast(`保存商品失败：${error.message}`)}finally{setBusy(false)}
 };
 const replaceUnit=async()=>{
  if(!unitWarning)return;
  setBusy(true);try{const result=await replaceProductUnitV2(unitWarning.draft);setUnitWarning(null);close();await refresh();toast(`已新建 ${result.newProduct.name}（${result.newProduct.unit}）；原 ${unitWarning.original.unit} 商品已停用`)}catch(error:any){toast(`变更单位失败：${error.message}`)}finally{setBusy(false)}
 };
 const toggleActive=async(product:Product)=>{
  if(product.active&&product.reminder&&!confirm("停用商品后，它将不再出现在新采购、盘点和补货选择中，同时关闭该商品的未完成补货提醒。历史记录与统计不会受影响。是否继续？"))return;
  setBusy(true);try{await setProductActiveV2(product.id,!product.active);await refresh();toast(product.active?"商品已停用；历史记录仍保留":"商品已重新启用")}catch(error:any){toast(`更新商品状态失败：${error.message}`)}finally{setBusy(false)}
 };
 const openPrice=(product:Product)=>{sessionStorage.setItem("report-product-id",String(product.id));sessionStorage.setItem("report-open-price","1");go("reports")};
 return <>
  <div className="head"><div><h1>商品管理</h1><p>详细采购、盘点和补货提醒的基础资料；桌面版从关系表直接查询</p></div><div><button className="btn" onClick={openNew}>＋ 新增商品</button></div></div>
  <div className="filters"><div className="search">⌕<input value={q} onChange={event=>setQ(event.target.value)} placeholder="搜索商品、分类、品牌、规格或单位"/></div><span>{loading?"正在查询…":`共 ${items.length} 个商品`}</span></div>
  <div className="panel"><table><thead><tr><th>商品名称</th><th>类别</th><th>品牌 / 规格</th><th>单位</th><th>参与盘点</th><th>补货提醒</th><th>状态</th><th>操作</th></tr></thead><tbody>{items.map(product=><tr key={product.id} className={product.active?"":"inactive-product"}><td><b>{product.name}</b></td><td>{product.category}</td><td>{product.brand} {product.spec}</td><td>{product.unit}</td><td><span className={product.stocktake?"yes":"no"}>{product.stocktake?"是":"否"}</span></td><td><span className={product.reminder?"yes":"no"}>{product.reminder?"已启用":"未启用"}</span></td><td><span className={product.active?"yes":"tag"}>{product.active?"启用":"已停用"}</span></td><td className="product-actions"><button className="link" onClick={()=>openEdit(product)}>编辑</button><button className="link" onClick={()=>openPrice(product)}>价格历史</button><button className="link" disabled={busy} onClick={()=>toggleActive(product)}>{product.active?"停用":"启用"}</button></td></tr>)}</tbody></table>{!loading&&!items.length&&<div className="empty-state">没有找到匹配的商品。</div>}</div>
  {dialog&&<div className="shade" onMouseDown={event=>event.currentTarget===event.target&&close()}><div className="modal"><div><h2>{dialog==="new"?"新增商品":"编辑商品档案"}</h2><button onClick={close}>×</button></div><div className="snapshot-notice"><b>历史数据保护</b><span>名称、类别、品牌和规格只影响新业务。已有历史的商品变更计量单位时，会新建商品并停用旧商品，旧采购继续保留原单位快照。</span></div><label>商品名称<input autoFocus value={draft.name} onChange={event=>setDraft({...draft,name:event.target.value})}/></label><label>商品类别<select value={draft.category} onChange={event=>setDraft({...draft,category:event.target.value})}>{categories.map(category=><option key={category}>{category}</option>)}</select></label><div className="product-form-row"><label>品牌<input value={draft.brand} onChange={event=>setDraft({...draft,brand:event.target.value})} placeholder="选填"/></label><label>规格<input value={draft.spec} onChange={event=>setDraft({...draft,spec:event.target.value})} placeholder="选填"/></label><label>计量单位<select value={draft.unit} onChange={event=>setDraft({...draft,unit:event.target.value})}>{units.map(unit=><option key={unit}>{unit}</option>)}</select></label></div><div className="product-switches"><label><input type="checkbox" checked={draft.stocktake} onChange={event=>setDraft({...draft,stocktake:event.target.checked})}/>参与盘点</label><label><input type="checkbox" checked={draft.reminder} onChange={event=>setDraft({...draft,reminder:event.target.checked})}/>启用补货提醒</label></div><footer><button className="btn soft" onClick={close}>取消</button><button className="btn" disabled={busy} onClick={save}>{busy?"正在保存…":"保存"}</button></footer></div></div>}
  {unitWarning&&<div className="shade"><div className="modal"><div><h2>计量单位变更</h2><button onClick={()=>setUnitWarning(null)}>×</button></div><div className="snapshot-notice"><b>该商品已有历史记录</b><span>不能直接把历史中的“{unitWarning.original.unit}”改成“{unitWarning.draft.unit}”。系统将新建一个“{unitWarning.draft.unit}”商品并停用旧商品，历史采购、价格和盘点仍引用旧商品。</span></div><p>原商品：<b>{unitWarning.original.name}（{unitWarning.original.unit}）</b></p><p>新商品：<b>{unitWarning.draft.name}（{unitWarning.draft.unit}）</b></p><footer><button className="btn soft" onClick={()=>setUnitWarning(null)}>返回修改</button><button className="btn" disabled={busy} onClick={replaceUnit}>{busy?"正在处理…":"新建并停用旧商品"}</button></footer></div></div>}
 </>;
}

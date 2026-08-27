/* eslint-disable @typescript-eslint/no-explicit-any */
import {desktopRequest} from "./desktop-api";

export type ExpenseQuery={
  start?:string;
  end?:string;
  category?:string;
  handler?:string;
  status?:string;
  keyword?:string;
  sortBy?:"date"|"amount"|"category"|"handler"|"mode"|"status"|"id";
  sortOrder?:"asc"|"desc";
  page?:number;
  pageSize?:number;
};

export type ReportQuery={
  start:string;
  end:string;
  keyword?:string;
  sortBy?:string;
  sortOrder?:"asc"|"desc";
  page?:number;
  pageSize?:number;
};

function queryString(values:Record<string,unknown>){
  const params=new URLSearchParams();
  for(const [key,value] of Object.entries(values)){
    if(value===undefined||value===null||value==="")continue;
    params.set(key,String(value));
  }
  const query=params.toString();
  return query?`?${query}`:"";
}

export async function queryExpensesV2(query:ExpenseQuery={}){
  return desktopRequest<{items:any[];page:number;pageSize:number;total:number;totalPages:number;amountTotal:number}>(`v2/expenses${queryString(query)}`);
}

export async function recentExpensesV2(limit=20,status="有效"){
  return desktopRequest<{items:any[]}>(`v2/expenses/recent${queryString({limit,status})}`);
}

export async function createExpenseV2(item:any){
  return desktopRequest<{item:any}>("v2/expenses/create",{method:"POST",body:JSON.stringify(item)});
}

export async function createPurchaseV2(payload:any){
  return desktopRequest<{purchaseNo:string;items:any[];lineCount:number;amount:number}>("v2/purchases/create",{method:"POST",body:JSON.stringify(payload)});
}

export async function updateExpenseV2(id:number,patch:any){
  return desktopRequest<{item:any}>("v2/expenses/update",{method:"POST",body:JSON.stringify({id,patch})});
}

export async function voidExpenseV2(id:number){
  return desktopRequest<{item:any}>("v2/expenses/void",{method:"POST",body:JSON.stringify({id})});
}

export async function listProductsV2(q="",active?:boolean,limit=500){
  return desktopRequest<{items:any[]}>(`v2/products${queryString({q,active,limit})}`);
}

export async function upsertProductV2(item:any){
  return desktopRequest<{item:any}>("v2/products/upsert",{method:"POST",body:JSON.stringify(item)});
}

export async function productHistoryStatusV2(id:number){
  return desktopRequest<{hasHistory:boolean}>(`v2/products/history-status${queryString({id})}`);
}

export async function setProductActiveV2(id:number,active:boolean){
  return desktopRequest<{item:any}>("v2/products/active",{method:"POST",body:JSON.stringify({id,active})});
}

export async function replaceProductUnitV2(item:any){
  return desktopRequest<{oldId:number;newProduct:any}>("v2/products/replace-unit",{method:"POST",body:JSON.stringify(item)});
}

export async function listIncomeV2(start="",end="",limit=1000){
  return desktopRequest<{items:any[]}>(`v2/income${queryString({start,end,limit})}`);
}

export async function upsertIncomeV2(item:any){
  return desktopRequest<{item:any}>("v2/income/upsert",{method:"POST",body:JSON.stringify(item)});
}

export async function dashboardV2(date?:string){
  return desktopRequest<{todayIncome:number;todayExpense:number;monthIncome:number;monthExpense:number;monthBalance:number}>(`v2/dashboard${queryString({date})}`);
}

export async function reportSummaryV2(start:string,end:string){
  return desktopRequest<{income:number;expense:number;balance:number}>(`v2/reports/summary${queryString({start,end})}`);
}

export async function reportOptionsV2(){
  return desktopRequest<{categories:string[];handlers:string[];products:any[]}>("v2/reports/options");
}

export async function reportExpensesV2(query:ExpenseQuery={}){
  return desktopRequest<{items:any[];page:number;pageSize:number;total:number;totalPages:number;amountTotal:number}>(`v2/reports/expenses${queryString(query)}`);
}

export async function reportIncomeV2(query:ReportQuery){
  return desktopRequest<{items:any[];page:number;pageSize:number;total:number;totalPages:number}>(`v2/reports/income${queryString(query)}`);
}

export async function reportSalesV2(query:ReportQuery){
  return desktopRequest<{items:any[];page:number;pageSize:number;total:number;totalPages:number}>(`v2/reports/sales${queryString(query)}`);
}

export async function reportStockV2(query:ReportQuery){
  return desktopRequest<{items:any[];page:number;pageSize:number;total:number;totalPages:number}>(`v2/reports/stock${queryString(query)}`);
}

export async function reportPricesV2(productId:number,query:ReportQuery){
  return desktopRequest<{items:any[];page:number;pageSize:number;total:number;totalPages:number;product:any;summary:{min:number;max:number;latest:number;average:number}}>(`v2/reports/prices${queryString({productId,...query})}`);
}

export async function exportAllV2(format:"xlsx"|"zip",start="",end=""){
  return desktopRequest<{path:string;cancelled?:boolean}>("v2/export/all",{method:"POST",body:JSON.stringify({format,start,end})});
}

export async function exportExpensesV2(query:ExpenseQuery={}){
  return desktopRequest<{path:string;cancelled?:boolean}>("v2/export/expenses",{method:"POST",body:JSON.stringify(query)});
}

export async function selectImportFileV2(){
  return desktopRequest<{path:string}>("v2/import/select",{method:"POST",body:"{}"});
}

export async function saveImportTemplateV2(){
  return desktopRequest<{path:string;cancelled?:boolean}>("v2/import/template",{method:"POST",body:"{}"});
}

export async function previewImportV2(path:string){
  return desktopRequest<{preview:any}>("v2/import/preview",{method:"POST",body:JSON.stringify({path})});
}

export async function applyImportV2(path:string,createUnknownProducts:boolean,importDuplicateQuickExpenses:boolean){
  return desktopRequest<{batchId:string;counts:any}>("v2/import/apply",{
    method:"POST",
    body:JSON.stringify({path,createUnknownProducts,importDuplicateQuickExpenses}),
  });
}

export async function storageStatusV2(verify=false){
  return desktopRequest<any>(verify?"v2/storage/verify":"v2/storage/status");
}
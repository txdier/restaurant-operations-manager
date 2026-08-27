/* eslint-disable @typescript-eslint/no-explicit-any */
import {desktopRequest} from "./desktop-api";

function query(values:Record<string,unknown>){
 const params=new URLSearchParams();
 for(const [key,value] of Object.entries(values))if(value!==undefined&&value!==null&&value!=="")params.set(key,String(value));
 const text=params.toString();
 return text?`?${text}`:"";
}

export async function dashboardDetailV2(date?:string){
 return desktopRequest<{todayIncome:number;todayExpense:number;monthIncome:number;monthExpense:number;monthBalance:number;pendingReminders:number;trend:any[];categories:any[]}>(`v2/dashboard/detail${query({date})}`);
}

export async function getSalesV2(date:string){
 return desktopRequest<{id:number|null;date:string;rows:any[];categories:any[];dailyIncome:number}>(`v2/sales${query({date})}`);
}

export async function saveSalesV2(date:string,rows:any[]){
 return desktopRequest<{item:any}>("v2/sales/save",{method:"POST",body:JSON.stringify({date,rows})});
}

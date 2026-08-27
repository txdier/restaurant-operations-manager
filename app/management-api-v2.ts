/* eslint-disable @typescript-eslint/no-explicit-any */
import {desktopRequest} from "./desktop-api";

function query(values:Record<string,unknown>){
 const params=new URLSearchParams();
 for(const [key,value] of Object.entries(values))if(value!==undefined&&value!==null&&value!=="")params.set(key,String(value));
 const text=params.toString();
 return text?`?${text}`:"";
}

export async function stocktakeFormV2(date:string,kind:string){return desktopRequest<{id:number|null;date:string;kind:string;rows:any[]}>(`v2/stocktake/form${query({date,kind})}`)}
export async function saveStocktakeV2(payload:any){return desktopRequest<{item:any}>("v2/stocktake/save",{method:"POST",body:JSON.stringify(payload)})}

export async function listRemindersV2(){return desktopRequest<{items:any[];products:any[];summary:{overdue:number;future:number;done:number} }>("v2/reminders")}
export async function createReminderV2(payload:any){return desktopRequest<{item:any}>("v2/reminders/create",{method:"POST",body:JSON.stringify(payload)})}
export async function finishReminderV2(id:number){return desktopRequest<{item:any}>("v2/reminders/finish",{method:"POST",body:JSON.stringify({id})})}
export async function deleteReminderV2(id:number){return desktopRequest("v2/reminders/delete",{method:"POST",body:JSON.stringify({id})})}

export async function listEmployeesV2(){return desktopRequest<{items:any[]}>("v2/employees")}
export async function upsertEmployeeV2(payload:any){return desktopRequest<{item:any}>("v2/employees/upsert",{method:"POST",body:JSON.stringify(payload)})}
export async function getPayrollV2(month:string){return desktopRequest<{month:string;confirmed:boolean;rows:any[];employees:any[]}>(`v2/payroll${query({month})}`)}
export async function generatePayrollV2(month:string){return desktopRequest<{item:any}>("v2/payroll/generate",{method:"POST",body:JSON.stringify({month})})}
export async function savePayrollV2(payload:any){return desktopRequest<{item:any}>("v2/payroll/save",{method:"POST",body:JSON.stringify(payload)})}

export async function listSuppliersV2(){return desktopRequest<{items:any[]}>("v2/suppliers")}
export async function upsertSupplierV2(payload:any){return desktopRequest<{item:any}>("v2/suppliers/upsert",{method:"POST",body:JSON.stringify(payload)})}

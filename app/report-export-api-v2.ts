/* eslint-disable @typescript-eslint/no-explicit-any */
import {desktopRequest} from "./desktop-api";

export async function exportReportV2(kind:"expense"|"income"|"sales"|"stock"|"price",query:Record<string,any>){
  return desktopRequest<{path:string;cancelled?:boolean}>("v2/export/report",{
    method:"POST",
    body:JSON.stringify({kind,...query}),
  });
}

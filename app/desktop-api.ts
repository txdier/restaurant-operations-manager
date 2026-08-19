/* eslint-disable @typescript-eslint/no-explicit-any */
export type DesktopResponse<T=unknown>={ok:boolean;error?:string}&T;

let token="";
if(typeof window!=="undefined"){
  const params=new URLSearchParams(window.location.search);
  token=params.get("desktopToken")||"";
  if(token){sessionStorage.setItem("restaurant-desktop-token",token);history.replaceState({},"",window.location.pathname)}
  else token=sessionStorage.getItem("restaurant-desktop-token")||"";
}

export const isDesktop=()=>Boolean(token);

export async function desktopRequest<T=unknown>(path:string,options:RequestInit={}):Promise<DesktopResponse<T>>{
  if(!token)throw new Error("当前不是桌面运行环境");
  const response=await fetch(`/api/${path}`,{
    ...options,
    headers:{"Content-Type":"application/json","X-Restaurant-Token":token,...(options.headers||{})},
  });
  const result=await response.json() as DesktopResponse<T>;
  if(!response.ok||!result.ok)throw new Error(result.error||"操作失败");
  return result;
}

export async function loadDesktopState(){return (await desktopRequest<{state:any}>("state")).state}
export async function saveDesktopState(state:any,event="save_state"){return (await desktopRequest<{state:any}>("state",{method:"POST",body:JSON.stringify({state,event})})).state}

import type { Metadata } from "next";
import "./globals.css";
import "./updates.css";
import "./clarifications.css";
import "./export-updates.css";
import "./recent-expenses.css";
import "./product-edit.css";
import "./unit-history.css";
import "./purchase-picker.css";
import "./admin-management.css";
import "./category-dialog.css";
import "./import-ui.css";
import "./status-filter.css";
import "./lock-screen.css";
import "./branding.css";
import "./runtime-enhancements.css";
import RuntimeEnhancements from "./RuntimeEnhancements";
export const metadata:Metadata={title:"餐馆经营管理系统",description:"小餐馆收入、采购、盘点、工资与经营数据管理",other:{"codex-preview":"development"}};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="zh-CN"><body>{children}<RuntimeEnhancements/></body></html>}

import React from "react";
import {createRoot} from "react-dom/client";
import Home from "../../app/page";
import "../../app/globals.css";
import "../../app/updates.css";
import "../../app/clarifications.css";
import "../../app/export-updates.css";
import "../../app/recent-expenses.css";
import "../../app/product-edit.css";
import "../../app/unit-history.css";
import "../../app/purchase-picker.css";
import "../../app/admin-management.css";
import "../../app/category-dialog.css";

createRoot(document.getElementById("root")!).render(<React.StrictMode><Home/></React.StrictMode>);

import {readFile, readdir} from "node:fs/promises";
import path from "node:path";

const assetDirectory = path.resolve("desktop/restaurant_manager/web/assets");
const files = (await readdir(assetDirectory)).filter((name) => name.endsWith(".js"));
if (!files.length) throw new Error("Desktop JavaScript bundle was not generated");

const unsupported = /(?:\?\?=|\|\|=|&&=)/;
for (const file of files) {
  const source = await readFile(path.join(assetDirectory, file), "utf8");
  const match = source.match(unsupported);
  if (match) throw new Error(`${file} contains unsupported Qt WebEngine syntax: ${match[0]}`);
}

const cssFiles = (await readdir(assetDirectory)).filter((name) => name.endsWith(".css"));
if (!cssFiles.length) throw new Error("Desktop CSS bundle was not generated");
const css = (await Promise.all(cssFiles.map((file) => readFile(path.join(assetDirectory, file), "utf8")))).join("\n");
const pageSource = await readFile(path.resolve("app/page.tsx"), "utf8");
if (css.includes("input[type=date]") || pageSource.includes('type="date"')) {
  throw new Error("Desktop bundle must not rely on native date inputs");
}
const dateControl = css.match(/\.date-control\{([^}]*)\}/)?.[1] ?? "";
if (!dateControl.includes("grid-template-columns:minmax(0,1fr) 32px") || !dateControl.includes("width:128px")) {
  throw new Error("Desktop custom date control spacing is missing");
}
if (!css.includes(".date-trigger") || !css.includes(".date-calendar")) {
  throw new Error("Desktop custom date button or calendar panel is missing");
}

console.log(`Desktop Web compatibility check passed (${files.length} JavaScript and ${cssFiles.length} CSS bundle${cssFiles.length === 1 ? "" : "s"}).`);

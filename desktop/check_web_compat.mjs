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
console.log(`Desktop JavaScript compatibility check passed (${files.length} bundle${files.length === 1 ? "" : "s"}).`);

import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const root = fileURLToPath(new URL("../", import.meta.url));
const python = fileURLToPath(
  new URL(
    process.platform === "win32"
      ? "../.venv/Scripts/python.exe"
      : "../.venv/bin/python",
    import.meta.url,
  ),
);
const exported = spawnSync(
  python,
  [
    "-c",
    "import json; from planner.app import create_app; print(json.dumps(create_app().openapi(), sort_keys=True, indent=2))",
  ],
  { cwd: root, encoding: "utf8" },
);
if (exported.status !== 0)
  throw new Error(
    exported.stderr || exported.error?.message || "OpenAPI export failed",
  );
const schema = JSON.parse(exported.stdout);
const generated =
  "// Generated from the FastAPI OpenAPI schema. Run npm run api:generate.\n" +
  astToString(await openapiTS(schema));
const outputs = new Map([
  ["apps/web/src/api/openapi.json", JSON.stringify(schema, null, 2) + "\n"],
  ["apps/web/src/api/generated.ts", generated],
]);
for (const [path, content] of outputs) {
  const target = new URL("../" + path, import.meta.url);
  if (process.argv.includes("--check")) {
    if (readFileSync(target, "utf8").replaceAll("\r\n", "\n") !== content)
      throw new Error(`${path} is stale. Run npm run api:generate.`);
  } else writeFileSync(target, content);
}
console.log(
  process.argv.includes("--check")
    ? "OpenAPI and TypeScript client match the backend."
    : "OpenAPI and TypeScript client generated.",
);

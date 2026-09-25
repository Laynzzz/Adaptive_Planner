// Entry point for the real OIDC/PostgreSQL load driver used in Task 13.
// Python owns authentication, isolated DB lifecycle, arrivals and durable-job timings.
// `node tests/load/workload.js --describe` displays the frozen workload without running it.
const { readFileSync } = require("node:fs");
const { spawnSync } = require("node:child_process");
const { resolve } = require("node:path");
const root = resolve(__dirname, "../..");
const manifest = resolve(root, "benchmarks/manifests/load.json");
const spec = JSON.parse(readFileSync(manifest, "utf8"));
if (spec.duration_seconds !== 600 || spec.warmup_seconds <= 0) {
  throw new Error("Ten-minute measured duration after warmup is required");
}
if (process.argv.includes("--describe")) {
  console.log(
    JSON.stringify(
      {
        ...spec,
        actual_driver: "python -m benchmarks.load",
        authentication:
          "Real local Keycloak state/PKCE/session/CSRF for demo-a and demo-b",
        isolation: "Disposable PostgreSQL database, loopback API port 38001",
      },
      null,
      2,
    ),
  );
} else {
  const uv =
    process.platform === "win32" ? resolve(root, ".tools/bin/uv.exe") : "uv";
  const run = spawnSync(
    uv,
    ["run", "python", "-m", "benchmarks.load", "--manifest", manifest],
    {
      cwd: root,
      stdio: "inherit",
      shell: false,
    },
  );
  if (run.error) throw run.error;
  process.exit(run.status ?? 1);
}

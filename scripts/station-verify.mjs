#!/usr/bin/env node
// Bounded Python verification bridge accepted by BrainOps Station.
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

for (const path of [
  "tube_bridge/oauth.py",
  "tube_bridge/transport.py",
  "tests/test_oauth_contract.py",
]) {
  const digest = createHash("sha256").update(readFileSync(path)).digest("hex");
  console.log(`sha256 ${digest}  ${path}`);
}

const args = [
  "-m", "pytest", "tests", "-q",
  "--ignore=tests/test_distribution_integration.py",
  "--ignore=tests/test_docker_runtime.py",
];
const child = spawn("python3", args, {
  cwd: process.cwd(),
  env: { ...process.env, CI: "1", FORCE_COLOR: "0" },
  stdio: "inherit",
  shell: false,
});
child.on("error", (error) => {
  console.error(error.message);
  process.exit(1);
});
child.on("exit", (code, signal) => {
  if (signal) {
    console.error(`pytest terminated by ${signal}`);
    process.exit(1);
  }
  process.exit(code ?? 1);
});

#!/usr/bin/env node
// Bounded Python verification bridge accepted by BrainOps Station.
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

for (const path of [
  "tube_bridge/server.py",
  "tube_bridge/transport.py",
  "tube_bridge/corpus.py",
  "tube_bridge/youtube/transcript.py",
  "tests/test_self_hosted_only_contract.py",
  ".brainops/methodology/frozen-tests/frozen-tdd-wi-00028-core-publication-001-python.json",
  ".brainops/methodology/frozen-tests/frozen-20260809051810-test_self_hosted_only_contract.py.json",
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

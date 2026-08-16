import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import tubeBridgePiExtension, {
  buildSafeEnvironment,
  loadPackageVersion,
  loadPortableServerConfig,
  mcpContentToPi,
  sanitizeError,
} from "../extensions/pi.ts";


test("portable config and package identity remain canonical", () => {
  const dataRoot = path.join(tmpdir(), "tube-bridge-pi-config");
  const server = loadPortableServerConfig(dataRoot);

  assert.equal(loadPackageVersion(), "1.1.5");
  assert.equal(server.command, "python3");
  assert.deepEqual(server.args, ["-m", "tube_bridge.cli"]);
  assert.equal(server.cwd, fileURLToPath(new URL("..", import.meta.url)));
  assert.equal(server.env.PLUGIN_ROOT, server.cwd);
  assert.equal(server.env.PLUGIN_DATA, dataRoot);
  assert.equal(server.env.TUBE_BRIDGE_CACHE, path.join(dataRoot, "cache"));
});


test("safe child environment excludes unrelated parent secrets", () => {
  const env = buildSafeEnvironment({
    PATH: "/usr/bin",
    HOME: "/tmp/home",
    YOUTUBE_API_KEY: "allowed-youtube-key",
    TUBE_BRIDGE_AUTH_KEY: "private-bearer-must-not-cross",
    UNRELATED_SECRET: "must-not-cross",
  });

  assert.equal(env.PATH, "/usr/bin");
  assert.equal(env.HOME, "/tmp/home");
  assert.equal(env.YOUTUBE_API_KEY, "allowed-youtube-key");
  assert.equal(env.PYTHONUNBUFFERED, "1");
  assert.ok(!("TUBE_BRIDGE_AUTH_KEY" in env));
  assert.ok(!("UNRELATED_SECRET" in env));
});


test("MCP content mapping preserves bounded text, resources, and images", () => {
  const mapped = mcpContentToPi({
    content: [
      { type: "text", text: "hello" },
      { type: "resource", resource: { text: "evidence" } },
      { type: "image", data: "aGVsbG8=", mimeType: "image/jpeg" },
    ],
  });

  assert.deepEqual(mapped, [
    { type: "text", text: "hello" },
    { type: "text", text: "evidence" },
    { type: "image", data: "aGVsbG8=", mimeType: "image/jpeg" },
  ]);

  const oversized = mcpContentToPi({
    content: [{ type: "image", data: "a".repeat(2_000_001), mimeType: "image/jpeg" }],
  });
  assert.equal(oversized[0].type, "text");
  assert.match(oversized[0].text, /Image omitted/);

  const structured = mcpContentToPi({ structuredContent: { ok: true } });
  assert.match(structured[0].text, /"ok": true/);

  const tooManyLines = mcpContentToPi({
    content: [{ type: "text", text: Array.from({ length: 2_100 }, (_, index) => `line-${index}`).join("\n") }],
  });
  assert.match(tooManyLines[0].text, /Output truncated/);
  assert.ok(tooManyLines[0].text.split("\n").length <= 2_002);
});


test("adapter errors redact credentials", () => {
  const message = sanitizeError(
    new Error("Bearer secret-value api_key=abc123 https://user:pass@example.test/path"),
  );

  assert.doesNotMatch(message, /secret-value|abc123|user:pass/);
  assert.match(message, /\[REDACTED\]/);
});


test("Pi host adapter discovers all MCP tools and preserves lifecycle commands", { timeout: 90_000 }, async () => {
  const tools = new Map();
  const commands = new Map();
  const handlers = new Map();
  const pi = {
    registerTool(definition) {
      tools.set(definition.name, definition);
    },
    registerCommand(name, definition) {
      commands.set(name, definition);
    },
    appendEntry() {},
    on(name, handler) {
      const values = handlers.get(name) ?? [];
      values.push(handler);
      handlers.set(name, values);
    },
  };
  const dataRoot = await mkdtemp(path.join(tmpdir(), "tube-bridge-pi-smoke-"));
  process.env.TUBE_BRIDGE_PI_DATA = dataRoot;

  tubeBridgePiExtension(pi);
  assert.deepEqual([...tools.keys()], ["tube_bridge_status"]);
  assert.deepEqual([...commands.keys()].sort(), ["tube-bridge-reconnect", "tube-bridge-selftest"]);

  try {
    for (const handler of handlers.get("session_start") ?? []) {
      await handler({ type: "session_start" }, { hasUI: false });
    }

    assert.equal(tools.size, 18, "expected status plus 17 MCP tools");
    assert.ok(tools.has("tube_bridge_tube_bridge_help"));

    const status = await tools.get("tube_bridge_status").execute(
      "status-call",
      {},
      new AbortController().signal,
    );
    assert.equal(status.details.discoveredTools, 17);
    assert.equal(status.details.version, "1.1.5");

    const help = await tools.get("tube_bridge_tube_bridge_help").execute(
      "help-call",
      {},
      new AbortController().signal,
    );
    const text = help.content.find((item) => item.type === "text")?.text;
    const payload = JSON.parse(text);
    assert.equal(payload.version, "1.1.5");
    assert.equal(payload.tools.length, 17);
  } finally {
    for (const handler of handlers.get("session_shutdown") ?? []) {
      await handler({ type: "session_shutdown" }, { hasUI: false });
    }
    delete process.env.TUBE_BRIDGE_PI_DATA;
    await rm(dataRoot, { recursive: true, force: true });
  }
});

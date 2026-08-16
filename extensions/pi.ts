import { mkdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { Type } from "typebox";

export const MAX_TEXT_BYTES = 50 * 1024;
export const MAX_TEXT_LINES = 2_000;
export const MAX_IMAGE_DATA_CHARS = 2_000_000;

const PACKAGE_ROOT = fileURLToPath(new URL("..", import.meta.url));
const TOOL_PREFIX = "tube_bridge_";
const CALL_TIMEOUT_MS = 180_000;
const SAFE_ENVIRONMENT_KEYS = [
  "PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "SHELL",
  "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "TUBE_BRIDGE_PROXY",
  "TUBE_BRIDGE_CACHE", "YOUTUBE_API_KEY",
] as const;

type PiContent =
  | { type: "text"; text: string }
  | { type: "image"; data: string; mimeType: string };

type PortableServerConfig = {
  command: string;
  args: string[];
  cwd: string;
  env: Record<string, string>;
};

function readJsonObject(url: URL, label: string): Record<string, unknown> {
  const value = JSON.parse(readFileSync(url, "utf8"));
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must contain a JSON object`);
  }
  return value as Record<string, unknown>;
}

export function loadPackageVersion(): string {
  const manifest = readJsonObject(new URL("../plugin.json", import.meta.url), "plugin.json");
  if (typeof manifest.version !== "string" || !manifest.version) {
    throw new Error("plugin.json must declare a non-empty version");
  }
  return manifest.version;
}

function resolvePluginData(environment: NodeJS.ProcessEnv = process.env): string {
  const configured = environment.TUBE_BRIDGE_PI_DATA?.trim();
  if (configured) return resolve(configured);
  const base = environment.XDG_DATA_HOME?.trim() || join(homedir(), ".local", "share");
  return resolve(base, "tube-bridge", "pi-plugin");
}

function expandPortableValue(value: string, dataRoot: string): string {
  const expanded = value
    .replaceAll("${PLUGIN_ROOT}", PACKAGE_ROOT)
    .replaceAll("${PLUGIN_DATA}", dataRoot);
  if (/\$\{[^}]+\}/.test(expanded)) {
    throw new Error(`unsupported placeholder in portable MCP value: ${value}`);
  }
  return expanded;
}

export function loadPortableServerConfig(
  dataRoot = resolvePluginData(),
): PortableServerConfig {
  const document = readJsonObject(new URL("../mcp.json", import.meta.url), "mcp.json");
  const servers = document.mcpServers;
  if (!servers || typeof servers !== "object" || Array.isArray(servers)) {
    throw new Error("mcp.json must declare mcpServers");
  }
  const entry = (servers as Record<string, unknown>)["tube-bridge"];
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
    throw new Error("mcp.json must declare the tube-bridge server");
  }
  const server = entry as Record<string, unknown>;
  if (server.type !== "stdio") {
    throw new Error("Pi adapter supports only the stdio package entry");
  }
  if (
    typeof server.command !== "string"
    || !server.command
    || /\s/.test(server.command)
    || server.command.includes("\0")
  ) {
    throw new Error("portable MCP command must be one executable token");
  }
  if (!Array.isArray(server.args) || server.args.some((value) => typeof value !== "string")) {
    throw new Error("portable MCP args must be an array of strings");
  }
  if (typeof server.cwd !== "string") {
    throw new Error("portable MCP cwd must be a string");
  }
  if (!server.env || typeof server.env !== "object" || Array.isArray(server.env)) {
    throw new Error("portable MCP env must be an object");
  }

  const env: Record<string, string> = {
    PLUGIN_ROOT: PACKAGE_ROOT,
    PLUGIN_DATA: dataRoot,
  };
  for (const [key, value] of Object.entries(server.env as Record<string, unknown>)) {
    if (key === "PLUGIN_ROOT" || key === "PLUGIN_DATA") {
      throw new Error(`${key} is reserved by the package host`);
    }
    if (typeof value !== "string") {
      throw new Error(`portable MCP env ${key} must be a string`);
    }
    env[key] = expandPortableValue(value, dataRoot);
  }

  return {
    command: server.command,
    args: (server.args as string[]).map((value) => expandPortableValue(value, dataRoot)),
    cwd: expandPortableValue(server.cwd, dataRoot),
    env,
  };
}

export function buildSafeEnvironment(
  parent: NodeJS.ProcessEnv = process.env,
): Record<string, string> {
  const child: Record<string, string> = { PYTHONUNBUFFERED: "1" };
  for (const key of SAFE_ENVIRONMENT_KEYS) {
    const value = parent[key];
    if (value) child[key] = value;
  }
  return child;
}

export function sanitizeError(error: unknown): string {
  return (error instanceof Error ? error.message : String(error))
    .replace(/Bearer\s+\S+/gi, "Bearer [REDACTED]")
    .replace(/(api[_-]?key|token|secret|password)\s*[=:]\s*\S+/gi, "$1=[REDACTED]")
    .replace(/https?:\/\/[^\s:@]+:[^\s@]+@/gi, "[REDACTED_PROXY]");
}

function truncateText(text: string): string {
  const lines = text.split("\n");
  let bounded = lines.length > MAX_TEXT_LINES
    ? lines.slice(0, MAX_TEXT_LINES).join("\n")
    : text;
  const encoded = Buffer.from(bounded, "utf8");
  if (encoded.length > MAX_TEXT_BYTES) {
    bounded = encoded.subarray(0, MAX_TEXT_BYTES).toString("utf8");
    while (Buffer.byteLength(bounded, "utf8") > MAX_TEXT_BYTES) {
      bounded = bounded.slice(0, -1);
    }
  }
  const truncated = lines.length > MAX_TEXT_LINES
    || Buffer.byteLength(text, "utf8") > MAX_TEXT_BYTES;
  return truncated
    ? `${bounded}\n\n[Output truncated: ${Math.min(lines.length, MAX_TEXT_LINES)}/${lines.length} lines.]`
    : bounded;
}

export function mcpContentToPi(result: any): PiContent[] {
  const content: PiContent[] = [];
  for (const item of result?.content ?? []) {
    if (item?.type === "text" && typeof item.text === "string") {
      content.push({ type: "text", text: truncateText(item.text) });
      continue;
    }
    if (
      item?.type === "image"
      && typeof item.data === "string"
      && typeof item.mimeType === "string"
    ) {
      content.push(item.data.length <= MAX_IMAGE_DATA_CHARS
        ? { type: "image", data: item.data, mimeType: item.mimeType }
        : {
            type: "text",
            text: `[Image omitted: ${item.data.length} base64 characters exceeds ${MAX_IMAGE_DATA_CHARS}.]`,
          });
      continue;
    }
    if (item?.type === "resource" && typeof item.resource?.text === "string") {
      content.push({ type: "text", text: truncateText(item.resource.text) });
      continue;
    }
    content.push({ type: "text", text: truncateText(JSON.stringify(item)) });
  }
  if (!content.length && result?.structuredContent !== undefined) {
    content.push({ type: "text", text: truncateText(JSON.stringify(result.structuredContent, null, 2)) });
  }
  return content.length
    ? content
    : [{ type: "text", text: "(tube-bridge returned no content)" }];
}

function contentErrorText(content: PiContent[]): string {
  return content
    .filter((item): item is { type: "text"; text: string } => item.type === "text")
    .map((item) => item.text)
    .join("\n") || "tube-bridge returned an MCP error";
}

export default function tubeBridgePiExtension(pi: ExtensionAPI) {
  const version = loadPackageVersion();
  let client: Client | undefined;
  let connecting: Promise<void> | undefined;
  let discoveredTools = 0;
  const registered = new Set<string>();

  async function closeClient(): Promise<void> {
    const current = client;
    client = undefined;
    if (current) await current.close().catch(() => undefined);
  }

  function registerMcpTool(tool: any): void {
    const mcpName = String(tool.name);
    const piName = `${TOOL_PREFIX}${mcpName.replace(/[^a-zA-Z0-9_]/g, "_")}`;
    if (registered.has(piName)) return;
    registered.add(piName);
    pi.registerTool({
      name: piName,
      label: `Tube Bridge · ${mcpName}`,
      description: `[local tube-bridge MCP] ${tool.description || mcpName}`,
      parameters: (tool.inputSchema ?? Type.Object({})) as any,
      async execute(_toolCallId, params, signal, onUpdate) {
        await ensureConnected();
        if (!client) throw new Error("tube-bridge MCP is not connected");
        try {
          const result = await client.callTool(
            { name: mcpName, arguments: params as Record<string, unknown> },
            undefined,
            {
              signal,
              timeout: CALL_TIMEOUT_MS,
              maxTotalTimeout: CALL_TIMEOUT_MS,
              onprogress(progress) {
                if (progress.total && onUpdate) {
                  onUpdate({
                    content: [{ type: "text", text: `tube-bridge ${mcpName}: ${progress.progress}/${progress.total}` }],
                    details: { server: "tube-bridge", tool: mcpName, progress },
                  });
                }
              },
            },
          );
          const content = mcpContentToPi(result);
          if ((result as any).isError) throw new Error(contentErrorText(content));
          return {
            content,
            details: {
              server: "tube-bridge",
              mcpTool: mcpName,
              version,
              imageCount: content.filter((item) => item.type === "image").length,
            },
          };
        } catch (error) {
          throw new Error(`tube-bridge ${mcpName}: ${sanitizeError(error)}`);
        }
      },
    });
  }

  async function ensureConnected(): Promise<void> {
    if (client) return;
    if (connecting) return connecting;
    connecting = (async () => {
      const server = loadPortableServerConfig();
      mkdirSync(server.env.PLUGIN_DATA, { recursive: true, mode: 0o700 });
      const nextClient = new Client({ name: "pi-tube-bridge", version });
      const transport = new StdioClientTransport({
        command: server.command,
        args: server.args,
        cwd: server.cwd,
        env: { ...server.env, ...buildSafeEnvironment() },
        stderr: "pipe",
        maxBufferSize: 4 * 1024 * 1024,
      });
      transport.stderr?.resume();
      try {
        await nextClient.connect(transport);
        const listing = await nextClient.listTools(undefined, { timeout: 60_000 });
        client = nextClient;
        discoveredTools = listing.tools.length;
        for (const tool of listing.tools) registerMcpTool(tool);
      } catch (error) {
        await nextClient.close().catch(() => undefined);
        throw new Error(`tube-bridge connection failed: ${sanitizeError(error)}`);
      }
    })();
    try {
      await connecting;
    } finally {
      connecting = undefined;
    }
  }

  pi.registerTool({
    name: "tube_bridge_status",
    label: "Tube Bridge Status",
    description: "Connect to the package-relative public tube-bridge runtime and report discovered tools.",
    parameters: Type.Object({}),
    async execute() {
      await ensureConnected();
      return {
        content: [{ type: "text", text: `tube-bridge ${version} connected: ${discoveredTools} MCP tools via local stdio` }],
        details: { connected: Boolean(client), discoveredTools, version, mode: "local" },
      };
    },
  });

  pi.registerCommand("tube-bridge-reconnect", {
    description: "Reconnect and rediscover the local tube-bridge MCP",
    handler: async (_args, ctx) => {
      await closeClient();
      try {
        await ensureConnected();
        if (ctx.hasUI) ctx.ui.notify(`tube-bridge ${version}: ${discoveredTools} tools`, "info");
      } catch (error) {
        if (ctx.hasUI) ctx.ui.notify(sanitizeError(error), "error");
      }
    },
  });

  pi.registerCommand("tube-bridge-selftest", {
    description: "Exercise local MCP discovery/help; add 'frame' for a live JPEG gate",
    handler: async (args, ctx) => {
      try {
        await ensureConnected();
        if (!client) throw new Error("tube-bridge MCP is not connected");
        const listing = await client.listTools(undefined, { timeout: 60_000 });
        const help = await client.callTool(
          { name: "tube_bridge_help", arguments: {} },
          undefined,
          { timeout: CALL_TIMEOUT_MS, maxTotalTimeout: CALL_TIMEOUT_MS },
        );
        const helpVersion = JSON.parse(contentErrorText(mcpContentToPi(help))).version ?? "unknown";
        let frameSummary = "frame=skipped";
        if (args.trim().toLowerCase() === "frame") {
          const frame = await client.callTool(
            {
              name: "youtube_get_frame",
              arguments: { url: "H6lZ182QaVk", timestamp_ms: 30_000, max_width: 640 },
            },
            undefined,
            { timeout: CALL_TIMEOUT_MS, maxTotalTimeout: CALL_TIMEOUT_MS },
          );
          const image = mcpContentToPi(frame).find(
            (item): item is { type: "image"; data: string; mimeType: string } => item.type === "image",
          );
          if (!image) throw new Error("frame self-test returned no image content");
          const bytes = Buffer.from(image.data, "base64");
          const jpeg = bytes.subarray(0, 2).equals(Buffer.from([0xff, 0xd8]))
            && bytes.subarray(-2).equals(Buffer.from([0xff, 0xd9]));
          if (!jpeg) throw new Error("frame self-test returned invalid JPEG bytes");
          frameSummary = `frame=image/jpeg:${bytes.length}B`;
        }
        const summary = `tube-bridge self-test PASS tools=${listing.tools.length} version=${helpVersion} ${frameSummary}`;
        pi.appendEntry("tube-bridge-selftest", { summary, at: new Date().toISOString() });
        if (ctx.hasUI) ctx.ui.notify(summary, "info");
      } catch (error) {
        const summary = `tube-bridge self-test FAIL: ${sanitizeError(error)}`;
        pi.appendEntry("tube-bridge-selftest", { summary, at: new Date().toISOString() });
        if (ctx.hasUI) ctx.ui.notify(summary, "error");
      }
    },
  });

  pi.on("session_start", async (_event, ctx) => {
    try {
      await ensureConnected();
      if (ctx.hasUI) ctx.ui.setStatus("tube-bridge", `tube-bridge ${version}: ${discoveredTools}`);
    } catch (error) {
      if (ctx.hasUI) ctx.ui.setStatus("tube-bridge", "tube-bridge: offline");
      if (ctx.hasUI) ctx.ui.notify(sanitizeError(error), "warning");
    }
  });

  pi.on("session_shutdown", async () => {
    await closeClient();
  });
}

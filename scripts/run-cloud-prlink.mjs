/**
 * Cursor Cloud Agent one-shot for zenapi PR dependency safety.
 * Invoked by zb-agent --prlink (cloud). Requires CURSOR_API_KEY and `npm install` in repo root.
 */
import { readFileSync } from "node:fs";
import { Agent } from "@cursor/sdk";

const [, , repoUrl, startingRef, promptPath] = process.argv;
if (!repoUrl || !startingRef || !promptPath) {
  console.error(
    "usage: node scripts/run-cloud-prlink.mjs <repoGitUrl> <startingRef> <promptFile>",
  );
  process.exit(2);
}

const apiKey = process.env.CURSOR_API_KEY;
if (!apiKey?.trim()) {
  console.error(
    "CURSOR_API_KEY is not set (create a key at https://cursor.com/dashboard/integrations ).",
  );
  process.exit(1);
}

const prompt = readFileSync(promptPath, "utf8");

try {
  const result = await Agent.prompt(prompt, {
    apiKey,
    cloud: {
      repos: [{ url: repoUrl, startingRef }],
      skipReviewerRequest: true,
    },
  });

  console.error("\n--- Cloud run finished ---");
  console.error("status:", result.status);
  if (result.id) console.error("run id:", result.id);
  if (result.result) {
    console.log(result.result);
  }
  if (result.status === "error") {
    process.exit(2);
  }
  if (result.status === "cancelled") {
    process.exit(3);
  }
  process.exit(0);
} catch (err) {
  console.error(err);
  process.exit(1);
}

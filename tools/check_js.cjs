"use strict";
// Check all first-party browser scripts, including dictionaries and stage modules.
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const root = path.join(__dirname, "..", "src", "spriteforge", "web");
function check(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.name === "vendor") continue;
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) check(filename);
    else if (entry.name.endsWith(".js")) {
      const result = spawnSync(process.execPath, ["--check", filename], { stdio: "inherit", windowsHide: true });
      if (result.status !== 0) process.exit(result.status || 1);
    }
  }
}
check(root);

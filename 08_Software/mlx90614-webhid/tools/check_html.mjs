#!/usr/bin/env node
// Dependency-free static check. This does NOT test the MCP2221A or MLX90614.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const targets = process.argv.slice(2);
const useDefaultTargets = !targets.length;
const projectRoot = fileURLToPath(new URL('../../../', import.meta.url));
if (useDefaultTargets) targets.push('08_Software/mlx90614-webhid/mlx.html', '99_Archive/webhid-history/03-dropdown-last-reading-baseline.html');
let failures = 0;

for (const name of targets) {
  const sourcePath = path.resolve(useDefaultTargets ? projectRoot : process.cwd(), name);
  try {
    const html = fs.readFileSync(sourcePath, 'utf8');
    const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)];
    const styles = [...html.matchAll(/<style\b([^>]*)>([\s\S]*?)<\/style\s*>/gi)];
    const issues = [];
    if (scripts.length !== 1) issues.push(`Expected one inline <script>, found ${scripts.length}.`);
    if (styles.length !== 1) issues.push(`Expected one inline <style>, found ${styles.length}.`);
    if (!html.includes('navigator.hid')) issues.push('No navigator.hid reference found.');
    if (!html.includes('MLX90614_ADDRESS')) issues.push('No MLX90614_ADDRESS constant found.');
    if (/<script\b[^>]*\bsrc\s*=/i.test(html)) issues.push('External <script src> found.');
    if (/<link\b[^>]*rel\s*=\s*["']?stylesheet/i.test(html)) issues.push('External stylesheet reference found.');
    if (scripts.length === 1) {
      if (scripts[0][1].trim()) issues.push('Inline script has unexpected attributes.');
      try { new vm.Script(scripts[0][2], { filename: `${name}:inline.js` }); }
      catch (error) { issues.push('JavaScript syntax error: ' + error.message); }
    }
    const checksum = crypto.createHash('sha256').update(html).digest('hex');
    if (issues.length) {
      failures += 1;
      console.error(`FAIL ${name}`);
      for (const issue of issues) console.error('  - ' + issue);
    } else {
      console.log(`PASS ${name}: ${Buffer.byteLength(html)} bytes; 1 inline JS + 1 inline CSS; syntax OK`);
      console.log(`     sha256 ${checksum}`);
    }
  } catch (error) {
    failures += 1;
    console.error(`FAIL ${name}: ${error.message}`);
  }
}

if (failures) process.exitCode = 1;

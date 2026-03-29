/**
 * electron-builder afterPack hook.
 * Copies bundled tessdata (.traineddata files) into the app's resources directory
 * after packaging, bypassing electron-builder's two-package-structure detection.
 */
const fs = require("fs");
const path = require("path");

module.exports = async function afterPack(context) {
  const srcDir = path.join(context.packager.projectDir, "tessdata");
  if (!fs.existsSync(srcDir)) {
    console.log("[afterPack] No tessdata/ directory found — skipping");
    return;
  }

  const destDir = path.join(context.appOutDir, "resources", "tessdata");
  fs.mkdirSync(destDir, { recursive: true });

  const files = fs.readdirSync(srcDir).filter((f) => f.endsWith(".traineddata"));
  for (const file of files) {
    const src = path.join(srcDir, file);
    const dst = path.join(destDir, file);
    fs.copyFileSync(src, dst);
    console.log(`[afterPack] Copied ${file} → resources/tessdata/`);
  }

  console.log(`[afterPack] Bundled ${files.length} tessdata files`);
};

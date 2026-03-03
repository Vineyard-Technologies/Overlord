"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const terser_1 = require("terser");
async function minifyFile(inputPath, outputPath) {
    try {
        const code = fs.readFileSync(inputPath, 'utf8');
        const result = await (0, terser_1.minify)(code, {
            compress: {
                dead_code: true,
                drop_console: false, // Keep console logs for debugging
                drop_debugger: true,
                keep_classnames: true,
                keep_fnames: false,
                passes: 2
            },
            mangle: {
                keep_classnames: true,
                keep_fnames: false
            },
            format: {
                comments: false
            }
        });
        if (result.code) {
            fs.writeFileSync(outputPath, result.code, 'utf8');
            const originalSize = fs.statSync(inputPath).size;
            const minifiedSize = fs.statSync(outputPath).size;
            const savings = ((1 - minifiedSize / originalSize) * 100).toFixed(1);
            console.log(`✓ Minified ${path.basename(inputPath)}: ${originalSize} → ${minifiedSize} bytes (${savings}% reduction)`);
        }
    }
    catch (error) {
        const err = error;
        console.error(`✗ Error minifying ${inputPath}:`, err.message);
        throw error;
    }
}
function copyDirectory(src, dest) {
    if (!fs.existsSync(dest)) {
        fs.mkdirSync(dest, { recursive: true });
    }
    const entries = fs.readdirSync(src, { withFileTypes: true });
    for (const entry of entries) {
        const srcPath = path.join(src, entry.name);
        const destPath = path.join(dest, entry.name);
        if (entry.isDirectory()) {
            copyDirectory(srcPath, destPath);
        }
        else {
            fs.copyFileSync(srcPath, destPath);
        }
    }
}
async function main() {
    console.log('Starting minification process...\n');
    // Create build-temp directory if it doesn't exist
    const tempDir = path.join(__dirname, 'build-temp');
    if (!fs.existsSync(tempDir)) {
        fs.mkdirSync(tempDir, { recursive: true });
    }
    // Minify main process file
    await minifyFile(path.join(__dirname, 'overlord.js'), path.join(tempDir, 'overlord.js'));
    // Minify renderer file
    await minifyFile(path.join(__dirname, 'renderer.js'), path.join(tempDir, 'renderer.js'));
    // Copy other files to temp directory
    console.log('\nCopying additional files...');
    // Copy HTML and CSS (no minification)
    fs.copyFileSync(path.join(__dirname, 'index.html'), path.join(tempDir, 'index.html'));
    console.log('✓ Copied index.html');
    fs.copyFileSync(path.join(__dirname, 'styles.css'), path.join(tempDir, 'styles.css'));
    console.log('✓ Copied styles.css');
    // Copy package.json without build config (electron-builder 3.0+ requirement)
    const packageJson = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8'));
    delete packageJson.build; // Remove build config from application package.json
    delete packageJson.devDependencies; // Remove dev dependencies
    fs.writeFileSync(path.join(tempDir, 'package.json'), JSON.stringify(packageJson, null, 2), 'utf8');
    console.log('✓ Copied package.json (without build config)');
    // Copy directories
    const dirsToCopy = ['images', 'fonts', 'scripts', 'templates'];
    for (const dir of dirsToCopy) {
        const srcDir = path.join(__dirname, dir);
        const destDir = path.join(tempDir, dir);
        if (fs.existsSync(srcDir)) {
            copyDirectory(srcDir, destDir);
            console.log(`✓ Copied ${dir}/ directory`);
        }
    }
    console.log('\n✓ Minification complete! Files are in build-temp/');
}
main().catch((error) => {
    console.error('Minification failed:', error);
    process.exit(1);
});

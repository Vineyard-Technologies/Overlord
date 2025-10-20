const toIco = require('to-ico');
const fs = require('fs');
const path = require('path');

const pngPath = 'C:/Users/Andrew/Downloads/overlordFavicon.png';
const outputPath = './build/icon.ico';

console.log('Converting PNG to ICO...');
console.log('Input:', pngPath);
console.log('Output:', outputPath);

const pngBuffer = fs.readFileSync(pngPath);

// Generate icon with multiple sizes for better quality at all resolutions
// Windows uses different sizes in different contexts:
// 16x16, 32x32 - Small icons in Explorer, taskbar, etc.
// 48x48 - Medium icons
// 256x256 - Large icons, required by electron-builder
toIco([pngBuffer], { sizes: [16, 32, 48, 256] })
  .then(buf => {
    fs.writeFileSync(outputPath, buf);
    console.log('✓ Icon created successfully!');
    console.log('Size:', buf.length, 'bytes');
    console.log('Resolutions included: 16x16, 32x32, 48x48, 256x256');
  })
  .catch(err => {
    console.error('✗ Error:', err);
    process.exit(1);
  });

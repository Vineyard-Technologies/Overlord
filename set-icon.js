const rcedit = require('rcedit');
const path = require('path');

const exePath = path.join(__dirname, 'dist', 'win-unpacked', 'Overlord.exe');
const iconPath = path.join(__dirname, 'build', 'icon.ico');

console.log('Setting icon for:', exePath);
console.log('Using icon:', iconPath);

rcedit(exePath, {
  icon: iconPath,
  'version-string': {
    'ProductName': 'Overlord',
    'FileDescription': 'Overlord - Asset Creation Pipeline Management Tool',
    'CompanyName': 'Vineyard Technologies',
    'LegalCopyright': 'Copyright © 2025 Vineyard Technologies',
    'OriginalFilename': 'Overlord.exe'
  }
})
.then(() => {
  console.log('✓ Icon and version info set successfully!');
})
.catch((err) => {
  console.error('✗ Error:', err);
  process.exit(1);
});

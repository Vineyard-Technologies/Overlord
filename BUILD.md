# Building Overlord Locally

This document describes how to build Overlord executable and installer locally using the new build script.

## Prerequisites

- Python 3.x installed
- Windows environment (for Inno Setup installer)

## Quick Start

Run the build script from the Overlord root directory:

```powershell
python scripts/build.py
```

The script will:
1. Prompt you for a version number (or use 'dev' as default)
2. Install required Python dependencies (PyInstaller, Pillow, psutil)
3. Build the executable using PyInstaller
4. Attempt to install Inno Setup if not present (via chocolatey)
5. Build the Windows installer
6. Clean up build artifacts

## Dependencies

The script will automatically install these Python packages:
- `pyinstaller` - For creating the executable
- `pillow` - Image processing library
- `psutil` - System and process utilities

For the installer, you'll need:
- **Inno Setup** - The script will try to install this via chocolatey, or you can install manually from https://jrsoftware.org/isinfo.php

## Output

After a successful build, you'll find:
- `dist/overlord.exe` - The standalone executable
- `dist/OverlordInstaller{version}.exe` - The Windows installer

## Manual Installation of Inno Setup

If chocolatey is not available, download and install Inno Setup manually:
1. Go to https://jrsoftware.org/isinfo.php
2. Download and install Inno Setup
3. Make sure `iscc.exe` is in your system PATH

## Troubleshooting

- If PyInstaller fails, ensure all dependencies are properly installed
- If Inno Setup can't be found, install it manually and ensure it's in your PATH
- The script requires write access to create files in the `src/` and root directories

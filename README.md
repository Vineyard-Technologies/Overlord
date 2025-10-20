![Overlord Logo](images/readmelogo.webp)
## An Asset Creation Pipeline Management Tool

Overlord uses Daz Studio, NVIDIA Iray, and Electron to generate 2D renders of 3D models for use in video games. Overlord provides both a GUI and command line interface for batch processing and automation.

![Overlord Screenshot](images/screenshot.webp)

## Installation

### Prerequisites
- **DAZ Studio 4.24+**: Download and install from [Daz3d.com](https://www.daz3d.com/get_studio)
- **Iray Server**: Download and install from [IrayPlugins.com](https://www.irayplugins.com/)
- **Node.js 18+**: Required for running from source or building locally. Download and install from [Node.js.org](https://nodejs.org/).

### Option 1: Install from Release (Recommended)
1. Browse to the [latest release](https://github.com/Vineyard-Technologies/Overlord/releases/latest)
2. Download and run the `OverlordInstaller` executable

### Option 2: Run from Source
1. Clone this repository:
   ```bash
   git clone https://github.com/Vineyard-Technologies/Overlord.git
   cd Overlord
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Run the application:
   ```bash
   npm start
   ```

## Usage

### Getting Started
1. Launch Overlord
2. Configure your **Source Sets** - folders containing your DAZ assets (.duf files)
3. Set your **Output Directory** - where rendered images will be saved
4. Adjust rendering parameters as needed
5. Click **Start Render** to begin

## Command Line Interface

Overlord supports extensive command line arguments for automation, testing, and batch processing.

### Basic Usage

```bash
npm start -- [options]
```

Or with the built executable:
```bash
overlord.exe [options]
```

### Command Line Options

#### Automation Flags
- `--startRender` - Automatically start render when application launches
- `--headless` - Run in headless mode without UI (automatically starts render)

#### Input File Arguments
- `--subject PATH` - Path to the subject .duf file
- `--animations PATH [PATH ...]` - One or more animation .duf files
- `--prop-animations PATH [PATH ...]` - One or more prop animation .duf files
- `--gear PATH [PATH ...]` - One or more gear .duf files
- `--gear-animations PATH [PATH ...]` - One or more gear animation .duf files
- `--output-dir PATH` - Output directory for rendered images

#### Render Settings
- `--instances N` - Number of render instances to run (default: 1)
- `--frame-rate N` - Frame rate for animations (default: 30)
- `--no-render-shadows` - Disable shadow rendering

#### Getting Help
- `npm start -- --help` - See all available command line options (development)
- `overlord.exe --help` - See all available command line options (executable)

### Usage Examples

#### GUI Mode with Auto-Start
```bash
# Launch GUI and automatically start render with saved settings
npm start -- --startRender

# Or with executable
overlord.exe --startRender

# Launch GUI with specific settings and auto-start
overlord.exe --subject "C:/Assets/character.duf" --animations "C:/Assets/attack.duf" --output-dir "C:/Output" --instances 2 --startRender
```

#### Headless Mode
```bash
# Basic headless render
overlord.exe --headless --subject "C:/Assets/character.duf" --animations "C:/Assets/attack.duf" --output-dir "C:/Output"

# Advanced headless render with multiple files and settings
overlord.exe --headless \
  --subject "C:/Assets/goblin.duf" \
  --animations "C:/Assets/attack.duf" "C:/Assets/idle.duf" \
  --gear "C:/Assets/sword.duf" "C:/Assets/shield.duf" \
  --output-dir "C:/Renders" \
  --instances 2 \
  --frame-rate 24
```

#### Required Arguments for Headless Mode
When using `--headless`, these arguments are required:
- `--subject` - Must specify a subject file
- `--animations` - Must specify at least one animation
- `--output-dir` - Must specify output directory

### Integration Examples

## GUI Features

### Source Sets
Source Sets are folders containing your DAZ asset files. Overlord recognizes these file types:
- `*_subject.duf` - This is a Scene Subset of either a figure or an object
- `*_animation.duf` - These are Pose Presets for the subject
- `*_gear.duf` - These are Wearables Presets for the subject
- `*_propAnimation.duf` - These are Pose Presets for objects included with the subject file
- `*_gearAnimation.duf` - These are Pose Presets for the gear files

## Utility Scripts

### Construct Zipper
The `constructZipper.js` script organizes rendered output files into organized zip archives by character, action, and rotation.

**Usage:**
```bash
npm run zip
```

This will scan the `~/Downloads/output` folder and create organized zip archives in `~/Downloads/output/ConstructZips/`.

**File Organization:**
- Input format: `prefix-action_rotation-sequence.extension` (e.g., `woman_shadow-powerUp_-67.5-014.webp`)
- Output structure: `ConstructZips/prefix/action/action_rotation.zip`
- Files with the same prefix, action, and rotation are grouped into a single zip file

## Building

To build a distributable Windows executable:

```bash
npm run build
```

This will create installers and portable executables in the `dist` folder using electron-builder.

## License
This project is licensed under the [AGPL 3.0 License](https://www.gnu.org/licenses/agpl-3.0.html.en) - see the [LICENSE](LICENSE) file for details.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## Support
For issues and support, please visit the [Issues](https://github.com/Vineyard-Technologies/Overlord/issues) page.

![Overlord Logo](images/readmelogo.webp)
## An Asset Creation Pipeline Management Tool

Overlord uses Daz Studio, NVIDIA Iray, Python, ImageMagick and PowerShell to generate 2D renders of 3D models, for use in video games. Overlord can be used both through its GUI, or the command line.

![Overlord Screenshot](images/screenshot.webp)

## Installation

### Prerequisites
- **DAZ Studio 4.24+**: Download and install from [Daz3d.com](https://www.daz3d.com/get_studio)
- **Iray Server**: Download and install from [IrayPlugins.com](https://www.irayplugins.com/)
- **ImageMagick**: Download and install from [ImageMagick.org](https://imagemagick.org/script/download.php)
- **Python 3.14+**: Required for running from source or building locally. Download and install from [Python.org](https://www.python.org/downloads/).

### Option 1: Install from Release (Recommended)
1. Browse to the [latest release](https://github.com/Vineyard-Technologies/Overlord/releases/latest)
2. Download and run the `OverlordInstaller` executable

### Option 2: Run from Source
1. Clone this repository:
   ```bash
   git clone https://github.com/Vineyard-Technologies/Overlord.git
   cd Overlord
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python src/overlord.py
   ```

## Usage

### Getting Started
1. Launch Overlord
2. Configure your **Source Sets** - folders containing your DAZ assets (.duf files)
3. Set your **Output Directory** - where rendered images will be saved
4. Adjust rendering parameters as needed
5. Click **Start Render** to begin

## Command Line Interface

Overlord supports extensive command line arguments for automation, testing, and batch processing. All arguments can be used with both the Python script and the compiled executable.

### Basic Usage

**Python (Development):**
```bash
python src/overlord.py [options]
```

**Executable:**
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
- `overlord.exe --help` - See all available command line options

### Usage Examples

#### GUI Mode with Auto-Start
```bash
# Launch GUI and automatically start render with saved settings
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

## License
This project is licensed under the [AGPL 3.0 License](https://www.gnu.org/licenses/agpl-3.0.html.en) - see the [LICENSE](LICENSE) file for details.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## Support
For issues and support, please visit the [Issues](https://github.com/Vineyard-Technologies/Overlord/issues) page.

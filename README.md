![Overlord Logo](images/readmelogo.png)
## An Asset Creation Pipeline Management Tool
![Overlord Screenshot](images/screenshot.png)


Overlord is a desktop application written in [Python](https://www.Python.org/) using [Tkinter](https://docs.python.org/3/library/tkinter.html) and [Pillow](https://pypi.org/project/pillow/). It creates assets for the ARPGs made by [Laserwolve Games](https://www.LaserwolveGames.com/), like [DaggerQuest](https://www.DaggerQuest.com/) and [Plains of Shinar](https://www.PlainsOfShinar.com/). It executes scripts written in [Daz Script 2](http://docs.daz3d.com/doku.php/public/software/dazstudio/4/referenceguide/scripting/start) and manages instances of [Daz Studio](https://www.daz3d.com/).

## Installation

### Prerequisites
- **DAZ Studio 4**: Download and install from [daz3d.com].(https://www.daz3d.com/get_studio)
- **Python 3.8+**: Required for running from source (not needed for executable). Download and install from [Python.org](https://www.python.org/downloads/).

### Option 1: Download Executable (Recommended)
1. Go to the [Releases](https://github.com/Laserwolve-Games/Overlord/releases) page
2. Download the latest `Overlord.exe` file
3. Run the executable directly - no installation required

### Option 2: Run from Source
1. Clone this repository:
   ```bash
   git clone https://github.com/Laserwolve-Games/Overlord.git
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

### Source Sets
Source Sets are folders containing your DAZ asset files. Overlord recognizes these file types:
- `*_subject.duf` - Character/subject files
- `*_animation.duf` - Animation files  
- `*_gear.duf` - Equipment/gear files
- `*_propAnimation.duf` - Prop animation files
- `*_gearAnimation.duf` - Gear animation files

### Settings
All your settings are automatically saved and restored when you restart Overlord:
- **Source Sets**: Your selected asset folders
- **Output Directory**: Where images are saved
- **Number of Instances**: How many DAZ Studio processes to run simultaneously
- **Frame Rate**: Animation frame rate for video exports
- **Log File Size**: Maximum size for log files
- **Render Shadows**: Whether to render shadow variants

### Features

#### Real-time Monitoring
- **Source Set Details**: Live count of assets in your source folders
- **Output Details**: Real-time statistics of your output folder
- **Last Rendered Image**: Preview of the most recently rendered image
- **Progress Tracking**: Visual progress bar and time estimates
- **Console Output**: Live feed of rendering status and operations

#### Rendering Management
- **Multi-instance Rendering**: Run multiple DAZ Studio instances for faster processing
- **Background Processing**: Continue working while renders run in background
- **Process Control**: Stop all DAZ Studio instances with one click
- **Shadow Variants**: Optionally render both normal and shadow versions

#### File Management
- **Auto-archiving**: Built-in ZIP compression for completed renders
- **Path Management**: Easy browsing and selection of folders
- **Settings Persistence**: All preferences saved automatically

### File Locations
- **Settings**: `%APPDATA%/Overlord/settings.json`
- **Logs**: `%APPDATA%/Overlord/log.txt`
- **Scripts**: `%APPDATA%/Overlord/scripts/` (when running as executable)

### Troubleshooting

#### DAZ Studio Not Found
- Ensure DAZ Studio is installed in the default location: `C:\Program Files\DAZ 3D\DAZStudio4\`
- Check that the executable exists at the expected path

#### Rendering Issues
- Verify your source sets contain valid `.duf` files
- Check the console output for error messages
- Review the log file at `%APPDATA%/Overlord/log.txt`

## License
This project is licensed under the [AGPL 3.0 License](https://www.gnu.org/licenses/agpl-3.0.html.en) - see the [LICENSE](LICENSE) file for details.

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## Support
For issues and support, please visit the [Issues](https://github.com/Laserwolve-Games/Overlord/issues) page.

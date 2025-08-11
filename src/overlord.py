import os
import sys
import subprocess
import shutil
import json
import logging
import datetime
import gc
import re
import webbrowser
import zipfile
import time
import threading
import warnings
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
import winreg
import psutil
import atexit
import tempfile
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from iray_server_actions import IrayServerActions
from version import __version__ as overlord_version

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

# Application constants
DEFAULT_MAX_WORKERS = 8
LOG_SIZE_MB = 100
RECENT_RENDER_TIMES_LIMIT = 25

# UI update intervals (milliseconds)
IMAGE_UPDATE_INTERVAL = 1000          # Legacy polling interval (deprecated)
OUTPUT_UPDATE_INTERVAL = 5000
AUTO_SAVE_DELAY = 2000

# Process startup delays (milliseconds)
DAZ_STUDIO_STARTUP_DELAY = 5000
OVERLORD_CLOSE_DELAY = 2000
IRAY_STARTUP_DELAY = 10000

# File extensions
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
SCENE_EXTENSIONS = ('.duf',)
ARCHIVE_EXTENSIONS = ('.zip', '.7z', '.rar')

# Default paths
DEFAULT_OUTPUT_SUBDIR = "Downloads/output"
APPDATA_SUBFOLDER = "Overlord"
SERVER_OUTPUT_SUBDIR = "Overlord Server Output"

# UI dimensions
SPLASH_WIDTH = 400
SPLASH_HEIGHT = 400
RIGHT_FRAME_SIZE = 1024
DETAILS_FRAME_WIDTH = 350
DETAILS_FRAME_HEIGHT = 200

# Theme colors
THEME_COLORS = {
    "light": {
        "bg": "#f0f0f0", "fg": "#000000", "entry_bg": "#ffffff", "entry_fg": "#000000",
        "button_bg": "#e1e1e1", "button_fg": "#000000", "frame_bg": "#f0f0f0",
        "text_bg": "#ffffff", "text_fg": "#000000", "select_bg": "#0078d4",
        "select_fg": "#ffffff", "highlight_bg": "#cccccc", "border": "#cccccc"
    },
    "dark": {
        "bg": "#2d2d30", "fg": "#ffffff", "entry_bg": "#3c3c3c", "entry_fg": "#ffffff",
        "button_bg": "#404040", "button_fg": "#ffffff", "frame_bg": "#2d2d30",
        "text_bg": "#1e1e1e", "text_fg": "#ffffff", "select_bg": "#0078d4",
        "select_fg": "#ffffff", "highlight_bg": "#404040", "border": "#555555"
    }
}

# Process names for monitoring
DAZ_STUDIO_PROCESSES = ['DAZStudio']
IRAY_SERVER_PROCESSES = ['iray_server.exe', 'iray_server_worker.exe']
WEBDRIVER_PROCESSES = ['geckodriver']

# Error messages
ERROR_MESSAGES = {
    "missing_source_files": "Please specify at least one Source File before starting the render.",
    "missing_output_dir": "Please specify an Output Directory before starting the render.",
    "daz_running_warning": "DAZ Studio is already running.\n\nDo you want to continue?",
    "daz_archive_warning": "DAZ Studio is currently running. Archiving while rendering may cause issues.\n\nDo you want to continue anyway?",
    "iray_config_failed": "Iray Server configuration failed",
    "render_start_failed": "Failed to start render",
}

# Validation limits
VALIDATION_LIMITS = {
    "max_instances": 16, "min_instances": 1, "max_frame_rate": 120, "min_frame_rate": 1,
    "max_log_size": 1000, "min_log_size": 1, "max_file_wait_time": 30, "png_stability_wait": 10,
}

# UI text constants
UI_TEXT = {
    "app_title": "Overlord", "options_header": "Options", "last_image_details": "Last Rendered Image Details",
    "output_details": "Output Details", "copy_path": "Copy Path", "start_render": "Start Render",
    "stop_render": "Stop Render", "zip_files": "Zip Outputted Files", "browse": "Browse", "clear": "Clear",
}

# Image processing constants
IMAGE_PROCESSING = {
    "transparent_crop_size": (2, 2), "dark_bg_color": (60, 60, 60, 255),
    "light_bg_color": (255, 255, 255, 255), "default_mode": "RGBA", "save_optimize": True
}

# Windows registry paths
WINDOWS_REGISTRY = {
    "theme_key": r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
    "theme_value": "AppsUseLightTheme"
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_app_data_path(subfolder: str = APPDATA_SUBFOLDER) -> str:
    """Get the application data path for the given subfolder."""
    appdata = os.environ.get('APPDATA')
    if appdata:
        return os.path.join(appdata, subfolder)
    else:
        return os.path.join(os.path.expanduser('~'), subfolder)

def get_local_app_data_path(subfolder: str = APPDATA_SUBFOLDER) -> str:
    """Get the local application data path for the given subfolder."""
    localappdata = os.environ.get('LOCALAPPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Local'))
    return os.path.join(localappdata, subfolder)

def get_server_output_directory() -> str:
    """Get the intermediate server output directory path."""
    return os.path.join(get_local_app_data_path(), SERVER_OUTPUT_SUBDIR)

def get_default_output_directory() -> str:
    """Get the default output directory for user files."""
    return os.path.join(os.path.expanduser("~"), DEFAULT_OUTPUT_SUBDIR)

def detect_windows_theme() -> str:
    """Detect if Windows is using dark or light theme."""
    try:
        # Check Windows registry for theme setting
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_REGISTRY['theme_key'])
        value, _ = winreg.QueryValueEx(registry_key, WINDOWS_REGISTRY['theme_value'])
        winreg.CloseKey(registry_key)
        return "light" if value else "dark"
    except Exception:
        # Default to light theme if detection fails
        return "light"

def format_file_size(size_bytes: int) -> str:
    """Format file size in bytes to human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        # When running from source, images are in the parent directory
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def ensure_directory_exists(directory: str) -> bool:
    """Ensure a directory exists, create if necessary."""
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"Failed to create directory {directory}: {e}")
        return False

def validate_file_path(file_path: str, must_exist: bool = True) -> bool:
    """Validate a file path."""
    if not file_path or not isinstance(file_path, str):
        return False
    
    if must_exist:
        return os.path.isfile(file_path)
    
    # Check if the directory exists (for new files)
    directory = os.path.dirname(file_path)
    return os.path.isdir(directory) if directory else True

def validate_directory_path(dir_path: str, must_exist: bool = True) -> bool:
    """Validate a directory path."""
    if not dir_path or not isinstance(dir_path, str):
        return False
    
    if must_exist:
        return os.path.isdir(dir_path)
    
    # For new directories, check if parent exists
    parent = os.path.dirname(dir_path)
    return os.path.isdir(parent) if parent else True

def get_directory_stats(directory: str) -> tuple:
    """Get directory statistics: total_size, png_count, zip_count, folder_count."""
    if not os.path.exists(directory):
        return 0, 0, 0, 0
    
    total_size = png_count = zip_count = folder_count = 0
    
    for rootdir, dirs, files in os.walk(directory):
        folder_count += len(dirs)
        for file in files:
            file_path = os.path.join(rootdir, file)
            try:
                file_size = os.path.getsize(file_path)
                total_size += file_size
                if file.lower().endswith('.png'):
                    png_count += 1
                elif file.lower().endswith('.zip'):
                    zip_count += 1
            except (OSError, IOError):
                continue
    
    return total_size, png_count, zip_count, folder_count

def find_newest_image(directory: str) -> list:
    """Find all images in directory sorted by modification time (newest first)."""
    image_files = []
    
    for rootdir, _, files in os.walk(directory):
        for fname in files:
            if fname.lower().endswith(IMAGE_EXTENSIONS):
                fpath = os.path.join(rootdir, fname)
                try:
                    mtime = os.path.getmtime(fpath)
                    image_files.append((mtime, fpath))
                except Exception:
                    continue
    
    # Sort by most recent first
    image_files.sort(reverse=True)
    return [fpath for mtime, fpath in image_files]


# ============================================================================
# PROCESS MANAGEMENT
# ============================================================================

def check_process_running(process_names: list) -> bool:
    """Check if any processes with the given names are running."""
    try:
        for proc in psutil.process_iter(['name']):
            try:
                proc_name = proc.info['name']
                if proc_name and any(name.lower() in proc_name.lower() for name in process_names):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return False

def kill_processes_by_name(process_names: list) -> int:
    """Kill all processes matching the given names. Returns count of killed processes."""
    killed_count = 0
    try:
        for proc in psutil.process_iter(['name']):
            try:
                proc_name = proc.info['name']
                if proc_name and any(name.lower() in proc_name.lower() for name in process_names):
                    proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logging.error(f'Failed to kill processes {process_names}: {e}')
    return killed_count

def is_daz_studio_running() -> bool:
    """Check if DAZ Studio processes are running."""
    return check_process_running(DAZ_STUDIO_PROCESSES)

def is_iray_server_running() -> bool:
    """Check if Iray Server processes are already running."""
    return check_process_running(IRAY_SERVER_PROCESSES)

def stop_iray_server() -> int:
    """Stop all iray_server.exe and iray_server_worker.exe processes."""
    killed_count = kill_processes_by_name(IRAY_SERVER_PROCESSES)
    if killed_count > 0:
        logging.info(f'Stopped {killed_count} Iray Server process(es)')
    return killed_count

def stop_all_render_processes() -> dict:
    """Stop all render-related processes. Returns counts of stopped processes."""
    logging.info('Stopping all render-related processes (DAZStudio, Iray Server, webdrivers)')
    
    results = {
        'daz_studio': kill_processes_by_name(DAZ_STUDIO_PROCESSES),
        'iray_server': stop_iray_server(),
        'webdrivers': kill_processes_by_name(WEBDRIVER_PROCESSES)
    }
    
    total = sum(results.values())
    logging.info(f'Stopped {total} total process(es): '
                f'{results["daz_studio"]} DAZ Studio, '
                f'{results["iray_server"]} Iray Server, '
                f'{results["webdrivers"]} webdriver')
    
    return results


# ============================================================================
# IMAGE PROCESSING
# ============================================================================

def wait_for_file_stability(file_path: str, max_wait_time: int = None) -> bool:
    """Wait for a file to be stable (fully written)."""
    if max_wait_time is None:
        max_wait_time = VALIDATION_LIMITS['max_file_wait_time']
    
    wait_time = 0
    while wait_time < max_wait_time:
        try:
            # Try to get file size twice with a small delay
            size1 = os.path.getsize(file_path)
            time.sleep(0.1)
            if not os.path.exists(file_path):
                return False
            size2 = os.path.getsize(file_path)
            if size1 == size2 and size1 > 0:
                return True
        except (OSError, FileNotFoundError):
            return False
        time.sleep(0.5)
        wait_time += 0.6
    return False

def is_image_transparent(image_path: str) -> bool:
    """Check if an image is entirely transparent."""
    try:
        with Image.open(image_path) as img:
            # Convert to RGBA if not already
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Get the alpha channel
            alpha_channel = img.split()[-1]
            
            # Check if all alpha values are 0 using numpy for efficiency
            alpha_array = np.array(alpha_channel)
            return np.all(alpha_array == 0)
    except Exception as e:
        logging.error(f"Error checking transparency for {image_path}: {e}")
        return False

def crop_transparent_image(image_path: str) -> bool:
    """Crop entirely transparent image to 2x2 pixels."""
    try:
        crop_size = IMAGE_PROCESSING['transparent_crop_size']
        logging.info(f"Cropping transparent image to {crop_size[0]}x{crop_size[1]}: {image_path}")
        
        # Create a new 2x2 transparent image
        cropped_img = Image.new('RGBA', crop_size, (0, 0, 0, 0))
        
        # Save the cropped image, overwriting the original
        cropped_img.save(image_path, 'PNG')
        logging.info(f"Successfully cropped transparent image: {image_path}")
        return True
    except Exception as e:
        logging.error(f"Error cropping transparent image {image_path}: {e}")
        return False

def process_transparent_image(png_path: str) -> str:
    """Check if image is entirely transparent and crop to 2x2 if needed."""
    if is_image_transparent(png_path):
        crop_transparent_image(png_path)
    return png_path

def remove_filename_suffixes(filename: str) -> tuple:
    """Remove '-Beauty' or '-gearCanvas' suffixes from filename."""
    name, ext = os.path.splitext(filename)
    original_name = name
    
    # Remove both '-gearCanvas' and '-Beauty' suffixes if present
    if name.endswith('-Beauty'):
        name = name[:-7]  # Remove '-Beauty' (7 characters)
    if name.endswith('-gearCanvas'):
        name = name[:-11]  # Remove '-gearCanvas' (11 characters)
    
    modified = name != original_name
    return name + ext if modified else filename, modified

def prepare_image_for_display(image_path: str, theme: str = "light"):
    """Prepare an image for display in tkinter with proper background handling."""
    try:
        # Verify image integrity first
        with Image.open(image_path) as verify_img:
            verify_img.verify()
        
        # Reopen for processing
        with Image.open(image_path) as img:
            img = img.convert("RGBA")
            
            # Handle transparency with theme-appropriate background
            if theme == "dark":
                bg_color = IMAGE_PROCESSING['dark_bg_color']
            else:
                bg_color = IMAGE_PROCESSING['light_bg_color']
            
            bg = Image.new("RGBA", img.size, bg_color)
            img = Image.alpha_composite(bg, img)
            
            # Create a copy to avoid keeping file handle open
            img_copy = img.copy()
        
        return ImageTk.PhotoImage(img_copy)
    except Exception as e:
        logging.error(f'Failed to prepare image for display {image_path}: {e}')
        return None

def get_image_info(image_path: str) -> tuple:
    """Get image dimensions and file size."""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
        file_size = os.path.getsize(image_path)
        return width, height, file_size
    except Exception as e:
        logging.error(f'Failed to get image info for {image_path}: {e}')
        return None, None, None


# ============================================================================
# ARCHIVE OPERATIONS
# ============================================================================

# ============================================================================
# ARCHIVE OPERATIONS
# ============================================================================

def archive_and_delete(inner_path: str, archive_path: str) -> None:
    """Archive a directory to zip and delete the original."""
    logging.info(f"Archiving {inner_path} to {archive_path}")
    try:
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
            for root, dirs, files in os.walk(inner_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, inner_path)
                    zipf.write(file_path, arcname)
        logging.info(f"Successfully archived {inner_path} to {archive_path}")
        try:
            shutil.rmtree(inner_path)
            logging.info(f"Deleted folder {inner_path}")
        except Exception as e:
            logging.error(f"Failed to delete folder {inner_path}: {e}")
    except Exception as e:
        logging.error(f"Failed to archive {inner_path}: {e}")

def archive_all_inner_folders(base_path: str) -> None:
    """Archive all inner folders in the structure base_path/*/*/* to zip, then delete the folder."""
    to_archive = []
    for folder_name in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder_name)
        if os.path.isdir(folder_path):
            for subfolder_name in os.listdir(folder_path):
                subfolder_path = os.path.join(folder_path, subfolder_name)
                if os.path.isdir(subfolder_path):
                    for inner_name in os.listdir(subfolder_path):
                        inner_path = os.path.join(subfolder_path, inner_name)
                        if os.path.isdir(inner_path):
                            archive_path = os.path.join(subfolder_path, f"{inner_name}.zip")
                            if not os.path.exists(archive_path):
                                to_archive.append((inner_path, archive_path))
    
    max_workers = min(int(os.environ.get('DEFAULT_MAX_WORKERS', DEFAULT_MAX_WORKERS)), os.cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        cleanup_manager.register_executor(executor)
        futures = [executor.submit(archive_and_delete, inner_path, archive_path) 
                  for inner_path, archive_path in to_archive]
        for future in as_completed(futures):
            try:
                future.result()  # Ensure any exceptions are raised here
            except Exception as e:
                logging.error(f"An error occurred while processing a future: {e}")


# ============================================================================
# APPLICATION SETUP AND LOGGING
# ============================================================================

def setup_logger() -> None:
    """Set up application logging."""
    # Try to write log to %APPDATA%/Overlord/log.txt (user-writable)
    log_dir = get_app_data_path()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'log.txt')
    from logging.handlers import RotatingFileHandler
    max_bytes = LOG_SIZE_MB * 1024 * 1024  # Convert MB to bytes
    file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=1, encoding='utf-8')
    stream_handler = logging.StreamHandler()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[file_handler, stream_handler]
    )
    logging.info(f'--- Overlord started --- (log file: {log_path}, max size: {LOG_SIZE_MB} MB)')

def create_splash_screen() -> tuple:
    """Create and show splash screen during startup."""
    splash = tk.Tk()
    splash.title(UI_TEXT["app_title"])
    splash.overrideredirect(True)  # Remove window decorations
    
    # Center the splash screen
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width - SPLASH_WIDTH) // 2
    y = (screen_height - SPLASH_HEIGHT) // 2
    splash.geometry(f"{SPLASH_WIDTH}x{SPLASH_HEIGHT}+{x}+{y}")
    
    try:
        # Load splash screen image
        splash_image = tk.PhotoImage(file=resource_path(os.path.join("images", "splashScreen.png")))
        splash_label = tk.Label(splash, image=splash_image)
        splash_label.image = splash_image  # Keep reference
        splash_label.pack(fill="both", expand=True)
    except Exception as e:
        # Fallback to text if image fails to load
        logging.warning(f"Could not load splash screen image: {e}")
        splash_label = tk.Label(splash, text=f"Overlord {overlord_version}\nRender Pipeline Manager\n\nStarting up...", 
                               font=("Arial", 16), bg="#2c2c2c", fg="white")
        splash_label.pack(fill="both", expand=True)
    
    # Add status text
    status_label = tk.Label(splash, text="Starting Overlord...", font=("Arial", 10), 
                           bg="#2c2c2c", fg="white")
    status_label.pack(side="bottom", pady=10)
    
    splash.update()
    return splash, status_label


# ============================================================================
# ENHANCED THEME MANAGER
# ============================================================================
# ============================================================================
# ENHANCED THEME MANAGER
# ============================================================================

class ThemeManager:
    """Enhanced theme management with better organization and features."""
    
    def __init__(self):
        self.current_theme = detect_windows_theme()
        self.themes = THEME_COLORS
        self.widgets_to_theme = []
        self.ttk_style = None
        
    def get_color(self, color_name: str) -> str:
        """Get a color value for the current theme."""
        return self.themes[self.current_theme][color_name]
    
    def setup_ttk_style(self) -> None:
        """Setup ttk styles for themed widgets."""
        if self.ttk_style is None:
            self.ttk_style = ttk.Style()
        
        # Configure progress bar style
        self.ttk_style.configure("Themed.Horizontal.TProgressbar",
                                background=self.get_color("select_bg"),
                                troughcolor=self.get_color("entry_bg"),
                                bordercolor=self.get_color("highlight_bg"),
                                lightcolor=self.get_color("select_bg"),
                                darkcolor=self.get_color("select_bg"))
    
    def register_widget(self, widget, widget_type: str = "default") -> None:
        """Register a widget to be themed."""
        self.widgets_to_theme.append((widget, widget_type))
        self.apply_theme_to_widget(widget, widget_type)
    
    def apply_theme_to_widget(self, widget, widget_type: str = "default") -> None:
        """Apply current theme to a specific widget."""
        try:
            if widget_type == "root":
                widget.configure(bg=self.get_color("bg"))
            elif widget_type == "frame":
                widget.configure(bg=self.get_color("frame_bg"))
            elif widget_type == "label":
                widget.configure(bg=self.get_color("bg"), fg=self.get_color("fg"))
            elif widget_type == "entry":
                widget.configure(bg=self.get_color("entry_bg"), fg=self.get_color("entry_fg"),
                               insertbackground=self.get_color("entry_fg"))
            elif widget_type == "text":
                widget.configure(bg=self.get_color("text_bg"), fg=self.get_color("text_fg"),
                               insertbackground=self.get_color("text_fg"),
                               selectbackground=self.get_color("select_bg"),
                               selectforeground=self.get_color("select_fg"))
            elif widget_type == "button":
                widget.configure(bg=self.get_color("button_bg"), fg=self.get_color("button_fg"),
                               activebackground=self.get_color("highlight_bg"),
                               activeforeground=self.get_color("fg"))
            elif widget_type == "checkbutton":
                widget.configure(bg=self.get_color("bg"), fg=self.get_color("fg"),
                               activebackground=self.get_color("bg"),
                               activeforeground=self.get_color("fg"),
                               selectcolor=self.get_color("entry_bg"))
            elif widget_type == "progressbar":
                # Apply ttk style to progress bar
                if self.ttk_style is None:
                    self.setup_ttk_style()
                widget.configure(style="Themed.Horizontal.TProgressbar")
            elif widget_type == "menu":
                widget.configure(bg=self.get_color("bg"), fg=self.get_color("fg"),
                               activebackground=self.get_color("select_bg"),
                               activeforeground=self.get_color("select_fg"),
                               selectcolor=self.get_color("entry_bg"))
        except Exception:
            # Some widgets might not support all options
            pass
    
    def apply_theme_to_all(self) -> None:
        """Apply current theme to all registered widgets."""
        if self.ttk_style is None:
            self.setup_ttk_style()
        for widget, widget_type in self.widgets_to_theme:
            self.apply_theme_to_widget(widget, widget_type)
    
    def get_border_color(self) -> str:
        """Get the border color for the current theme."""
        return self.get_color("border")
    
    def switch_theme(self, theme_name: str) -> bool:
        """Switch to a different theme."""
        if theme_name not in self.themes:
            logging.warning(f"Unknown theme: {theme_name}")
            return False
        
        self.current_theme = theme_name
        self.apply_theme_to_all()
        logging.info(f"Switched to {theme_name} theme")
        return True


# Global theme manager instance
theme_manager = ThemeManager()


# ============================================================================
# ENHANCED SETTINGS MANAGER
# ============================================================================

class SettingsValidator:
    """Validates settings values."""
    
    @staticmethod
    def validate_number_of_instances(value: str) -> bool:
        """Validate number of instances setting."""
        try:
            num = int(value)
            return VALIDATION_LIMITS['min_instances'] <= num <= VALIDATION_LIMITS['max_instances']
        except ValueError:
            return False
    
    @staticmethod
    def validate_frame_rate(value: str) -> bool:
        """Validate frame rate setting."""
        try:
            rate = int(value)
            return VALIDATION_LIMITS['min_frame_rate'] <= rate <= VALIDATION_LIMITS['max_frame_rate']
        except ValueError:
            return False
    
    @staticmethod
    def validate_log_file_size(value: str) -> bool:
        """Validate log file size setting."""
        try:
            size = int(value)
            return VALIDATION_LIMITS['min_log_size'] <= size <= VALIDATION_LIMITS['max_log_size']
        except ValueError:
            return False
    
    @staticmethod
    def validate_source_files(files: list) -> bool:
        """Validate source files list."""
        if not files:
            return False
        return all(validate_file_path(f, must_exist=True) for f in files)
    
    @staticmethod
    def validate_output_directory(directory: str) -> bool:
        """Validate output directory."""
        return validate_directory_path(directory, must_exist=False)

class SettingsManager:
    """Enhanced settings management with validation and better error handling."""
    
    def __init__(self):
        # Get settings file path in user directory
        self.settings_dir = get_app_data_path()
        os.makedirs(self.settings_dir, exist_ok=True)
        self.settings_file = os.path.join(self.settings_dir, 'settings.json')
        
        # Default settings
        self.default_settings = {
            "source_files": [],
            "output_directory": get_default_output_directory(),
            "number_of_instances": "1",
            "frame_rate": "30",
            "log_file_size": "100",
            "render_shadows": True
        }
    
    def load_settings(self) -> dict:
        """Load settings from file, return defaults if file doesn't exist or is corrupted."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    # Merge with defaults to handle new settings in updates
                    merged_settings = self.default_settings.copy()
                    merged_settings.update(settings)
                    logging.info(f'Settings loaded from {self.settings_file}')
                    return merged_settings
            else:
                logging.info('No settings file found, using defaults')
        except Exception as e:
            logging.warning(f'Failed to load settings: {e}, using defaults')
        
        return self.default_settings.copy()
    
    def save_settings(self, settings: dict) -> bool:
        """Save settings to file with validation."""
        try:
            # Basic validation before saving
            errors = self._validate_settings(settings)
            if errors:
                logging.warning(f'Settings validation warnings: {errors}')
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            logging.info(f'Settings saved to {self.settings_file}')
            return True
        except Exception as e:
            logging.error(f'Failed to save settings: {e}')
            return False
    
    def _validate_settings(self, settings: dict) -> list:
        """Validate settings and return list of issues."""
        issues = []
        
        if not SettingsValidator.validate_number_of_instances(settings.get('number_of_instances', '1')):
            issues.append("Invalid number of instances")
        
        if not SettingsValidator.validate_frame_rate(settings.get('frame_rate', '30')):
            issues.append("Invalid frame rate")
        
        if not SettingsValidator.validate_log_file_size(settings.get('log_file_size', '100')):
            issues.append("Invalid log file size")
        
        return issues
    
    def get_current_settings(self, value_entries: dict, render_shadows_var) -> dict:
        """Extract current settings from UI widgets."""
        try:
            source_files_text = value_entries["Source Files"].get("1.0", tk.END).strip()
            source_files = [f.strip() for f in source_files_text.split('\n') if f.strip()]
            
            return {
                "source_files": source_files,
                "output_directory": value_entries["Output Directory"].get(),
                "number_of_instances": value_entries["Number of Instances"].get(),
                "frame_rate": value_entries["Frame Rate"].get(),
                "log_file_size": value_entries["Log File Size (MBs)"].get(),
                "render_shadows": render_shadows_var.get()
            }
        except tk.TclError:
            # Widgets have been destroyed, return default settings
            logging.warning("Widgets destroyed during settings extraction, using defaults")
            return self.default_settings.copy()
    
    def apply_settings(self, settings: dict, value_entries: dict, render_shadows_var) -> bool:
        """Apply loaded settings to UI widgets."""
        try:
            # Source Files (text widget)
            value_entries["Source Files"].delete("1.0", tk.END)
            if settings["source_files"]:
                value_entries["Source Files"].insert("1.0", "\n".join(settings["source_files"]))
            
            # Output Directory
            value_entries["Output Directory"].delete(0, tk.END)
            value_entries["Output Directory"].insert(0, settings["output_directory"])
            
            # Number of Instances
            value_entries["Number of Instances"].delete(0, tk.END)
            value_entries["Number of Instances"].insert(0, settings["number_of_instances"])
            
            # Frame Rate
            value_entries["Frame Rate"].delete(0, tk.END)
            value_entries["Frame Rate"].insert(0, settings["frame_rate"])
            
            # Log File Size
            value_entries["Log File Size (MBs)"].delete(0, tk.END)
            value_entries["Log File Size (MBs)"].insert(0, settings["log_file_size"])
            
            # Checkboxes
            render_shadows_var.set(settings["render_shadows"])
            
            logging.info('Settings applied to UI')
            return True
        except Exception as e:
            logging.error(f'Failed to apply some settings: {e}')
            return False


# Global settings manager instance
settings_manager = SettingsManager()


# ============================================================================
# ENHANCED FILE MONITORING AND EXR CONVERSION
# ============================================================================

class ExrFileHandler(FileSystemEventHandler):
    """Enhanced EXR to PNG converter with better error handling and progress tracking."""
    
    def __init__(self, output_directory: str, update_gui_callback=None):
        super().__init__()
        self.output_directory = output_directory
        self.update_gui_callback = update_gui_callback
        self.image_update_callback = None  # New callback for UI image updates
        self.processed_files = set()
        self.conversion_queue = []
        self.conversion_thread = None
        self.stop_conversion = False
        self.final_output_directory = output_directory
        self.conversion_stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
    
    def set_image_update_callback(self, callback):
        """Set callback function to update UI when new images are available."""
        self.image_update_callback = callback
    
    def set_final_output_directory(self, final_output_directory: str):
        """Set the final output directory where processed PNGs should be moved."""
        self.final_output_directory = final_output_directory
    
    def on_created(self, event):
        """Handle new file creation events."""
        if not event.is_directory:
            if event.src_path.lower().endswith('.exr'):
                self.add_to_conversion_queue(event.src_path)
            elif event.src_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')):
                # Notify UI of new image file
                self._notify_image_update(event.src_path)
                if event.src_path.lower().endswith('.png'):
                    self.handle_png_file(event.src_path)
    
    def on_moved(self, event):
        """Handle file move events."""
        if not event.is_directory:
            if event.dest_path.lower().endswith('.exr'):
                self.add_to_conversion_queue(event.dest_path)
            elif event.dest_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')):
                # Notify UI of new image file
                self._notify_image_update(event.dest_path)
                if event.dest_path.lower().endswith('.png'):
                    self.handle_png_file(event.dest_path)
    
    def _notify_image_update(self, image_path: str):
        """Notify the UI that a new image is available."""
        if self.image_update_callback:
            try:
                # Schedule the UI update on the main thread
                self.image_update_callback(image_path)
            except Exception as e:
                logging.error(f"Error notifying UI of image update: {e}")
    
    def add_to_conversion_queue(self, exr_path: str):
        """Add EXR file to conversion queue."""
        if exr_path not in self.processed_files:
            self.conversion_queue.append(exr_path)
            self.processed_files.add(exr_path)
            logging.info(f'Added {exr_path} to EXR conversion queue')
            
            # Start conversion thread if not already running
            if self.conversion_thread is None or not self.conversion_thread.is_alive():
                self.start_conversion_thread()
    
    def start_conversion_thread(self):
        """Start the conversion thread."""
        self.stop_conversion = False
        self.conversion_thread = threading.Thread(target=self.process_conversion_queue, daemon=True)
        self.conversion_thread.start()
    
    def stop_conversion_thread(self):
        """Stop the conversion thread."""
        self.stop_conversion = True
        if self.conversion_thread and self.conversion_thread.is_alive():
            self.conversion_thread.join(timeout=5.0)
    
    def process_conversion_queue(self):
        """Process the conversion queue in a background thread."""
        while not self.stop_conversion:
            if self.conversion_queue:
                exr_path = self.conversion_queue.pop(0)
                try:
                    self.convert_exr_to_png(exr_path)
                except Exception as e:
                    logging.error(f'Failed to convert {exr_path} to PNG: {e}')
                    self.conversion_stats['failed'] += 1
            else:
                time.sleep(0.5)
    
    def convert_exr_to_png(self, exr_path: str) -> bool:
        """Convert a single EXR file to PNG with enhanced error handling."""
        try:
            self.conversion_stats['total'] += 1
            
            # Wait for file to be fully written
            if not self._wait_for_file_stability(exr_path):
                logging.warning(f'EXR file not stable or missing: {exr_path}')
                self.conversion_stats['skipped'] += 1
                return False
            
            # Validate EXR file before attempting conversion
            if not self._validate_exr_file(exr_path):
                logging.warning(f'EXR file appears to be corrupted or incomplete: {exr_path}')
                self.conversion_stats['failed'] += 1
                # Still try to clean up the corrupted file
                self._cleanup_exr_file(exr_path)
                return False
            
            # Generate PNG path
            png_path = os.path.splitext(exr_path)[0] + '.png'
            
            # Check if PNG already exists
            if os.path.exists(png_path):
                logging.info(f'PNG already exists, skipping conversion: {png_path}')
                self.conversion_stats['skipped'] += 1
                return True
            
            logging.info(f'Converting {exr_path} to {png_path}')
            
            # Try multiple methods to read the EXR file
            img = self._read_exr_file(exr_path)
            
            if img is None:
                logging.error(f'All methods failed to read EXR file: {exr_path}')
                self.conversion_stats['failed'] += 1
                # Clean up the failed EXR file
                self._cleanup_exr_file(exr_path)
                return False
            
            # Save as PNG with optimization
            self._save_png_file(img, png_path)
            
            # Handle PNG post-processing
            self._post_process_png(png_path)
            
            # Delete original EXR file to save space
            self._cleanup_exr_file(exr_path)
            
            self.conversion_stats['successful'] += 1
            logging.info(f'Successfully converted {exr_path} to {png_path}')
            return True
            
        except Exception as e:
            logging.error(f'Error converting {exr_path} to PNG: {e}')
            self.conversion_stats['failed'] += 1
            # Clean up the failed EXR file
            try:
                self._cleanup_exr_file(exr_path)
            except Exception:
                pass  # Ignore cleanup errors
            return False
    
    def _validate_exr_file(self, exr_path: str) -> bool:
        """Validate EXR file for basic correctness before attempting conversion."""
        try:
            # Check file size - corrupted EXR files often have unusual sizes
            if not os.path.exists(exr_path):
                return False
            
            file_size = os.path.getsize(exr_path)
            if file_size < 1024:  # Less than 1KB is likely corrupted
                logging.warning(f'EXR file too small ({file_size} bytes): {exr_path}')
                return False
            
            # Quick validation using imageio first (fastest method)
            try:
                import imageio.v3 as iio
                # Try to read just the metadata without loading the full image
                with iio.imopen(exr_path, 'r') as file:
                    meta = file.metadata()
                    # Check if we have reasonable dimensions
                    if hasattr(file, 'shape') and len(file.shape) >= 2:
                        height, width = file.shape[:2]
                        if height <= 0 or width <= 0 or height > 32768 or width > 32768:
                            logging.warning(f'EXR file has invalid dimensions ({width}x{height}): {exr_path}')
                            return False
                    return True
            except Exception as e:
                logging.debug(f'imageio validation failed for {exr_path}: {e}')
            
            # Fallback validation using basic file header check
            try:
                with open(exr_path, 'rb') as f:
                    # Read EXR magic number (first 4 bytes should be 0x762f3101)
                    magic = f.read(4)
                    if len(magic) != 4:
                        return False
                    
                    # Check EXR magic number
                    if magic != b'\x76\x2f\x31\x01':
                        logging.warning(f'EXR file has invalid magic number: {exr_path}')
                        return False
                    
                    return True
            except Exception as e:
                logging.debug(f'File header validation failed for {exr_path}: {e}')
                return False
                
        except Exception as e:
            logging.warning(f'EXR validation failed for {exr_path}: {e}')
            return False
    
    def _wait_for_file_stability(self, file_path: str, max_wait: int = 30) -> bool:
        """Wait for file to be stable and fully written."""
        wait_time = 0
        while wait_time < max_wait:
            try:
                if not os.path.exists(file_path):
                    return False
                    
                size1 = os.path.getsize(file_path)
                time.sleep(0.5)
                
                if not os.path.exists(file_path):
                    return False
                    
                size2 = os.path.getsize(file_path)
                if size1 == size2 and size1 > 0:
                    return True
                    
            except (OSError, FileNotFoundError):
                return False
                
            time.sleep(1)
            wait_time += 1
        
        return False
    
    def _read_exr_file(self, exr_path: str):
        """Try multiple methods to read EXR file with enhanced error handling."""
        # Method 1: imageio (with warning suppression for corrupted files)
        try:
            import imageio.v3 as iio
            import warnings
            
            # Suppress specific warnings about corrupted frame headers
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*claims there are .* frames, but there are actually .* frames.*")
                warnings.filterwarnings("ignore", message=".*tile cannot extend outside image.*")
                
                img_array = iio.imread(exr_path)
                
                # Validate the loaded image array
                if img_array is None or img_array.size == 0:
                    raise ValueError("Loaded image array is empty")
                
                # Check for reasonable dimensions
                if len(img_array.shape) < 2:
                    raise ValueError(f"Invalid image shape: {img_array.shape}")
                
                height, width = img_array.shape[:2]
                if height <= 0 or width <= 0:
                    raise ValueError(f"Invalid image dimensions: {width}x{height}")
            
            if img_array.dtype != 'uint8':
                img_array = np.clip(img_array, 0, 1)
                img_array = (img_array * 255).astype('uint8')
            
            if len(img_array.shape) >= 3 and img_array.shape[-1] == 4:
                return Image.fromarray(img_array, 'RGBA')
            else:
                if len(img_array.shape) == 2:
                    # Grayscale image, convert to RGB
                    img_array = np.stack([img_array, img_array, img_array], axis=2)
                return Image.fromarray(img_array, 'RGB')
                
        except Exception as e:
            logging.debug(f'imageio failed to read EXR: {e}')
        
        # Method 2: OpenEXR (if available)
        try:
            import OpenEXR
            import Imath
            
            exrfile = OpenEXR.InputFile(exr_path)
            header = exrfile.header()
            dw = header['dataWindow']
            width = dw.max.x - dw.min.x + 1
            height = dw.max.y - dw.min.y + 1
            
            # Validate dimensions
            if width <= 0 or height <= 0 or width > 32768 or height > 32768:
                raise ValueError(f"Invalid image dimensions: {width}x{height}")
            
            FLOAT = Imath.PixelType(Imath.PixelType.FLOAT)
            r_str = exrfile.channel('R', FLOAT)
            g_str = exrfile.channel('G', FLOAT)
            b_str = exrfile.channel('B', FLOAT)
            
            # Check for alpha channel
            try:
                a_str = exrfile.channel('A', FLOAT)
                has_alpha = True
            except:
                has_alpha = False
            
            # Convert to numpy arrays with validation
            expected_size = height * width * 4  # 4 bytes per float32
            if len(r_str) != expected_size or len(g_str) != expected_size or len(b_str) != expected_size:
                raise ValueError(f"Channel data size mismatch for {width}x{height} image")
            
            r = np.frombuffer(r_str, dtype=np.float32).reshape((height, width))
            g = np.frombuffer(g_str, dtype=np.float32).reshape((height, width))
            b = np.frombuffer(b_str, dtype=np.float32).reshape((height, width))
            
            if has_alpha:
                if len(a_str) != expected_size:
                    raise ValueError(f"Alpha channel data size mismatch for {width}x{height} image")
                a = np.frombuffer(a_str, dtype=np.float32).reshape((height, width))
                rgba = np.stack([r, g, b, a], axis=2)
                rgba = np.clip(rgba, 0, 1)
                rgba = (rgba * 255).astype(np.uint8)
                return Image.fromarray(rgba, 'RGBA')
            else:
                rgb = np.stack([r, g, b], axis=2)
                rgb = np.clip(rgb, 0, 1)
                rgb = (rgb * 255).astype(np.uint8)
                return Image.fromarray(rgb, 'RGB')
                
        except Exception as e:
            logging.debug(f'OpenEXR failed to read EXR: {e}')
        
        # Method 3: PIL (as last resort)
        try:
            img = Image.open(exr_path)
            # Validate the image
            if img.size[0] <= 0 or img.size[1] <= 0:
                raise ValueError(f"Invalid image dimensions: {img.size}")
            return img
        except Exception as e:
            logging.debug(f'PIL failed to read EXR: {e}')
        
        return None
    
    def _save_png_file(self, img, png_path: str):
        """Save image as PNG with appropriate format."""
        if img.mode == 'RGBA':
            img.save(png_path, 'PNG', optimize=True)
        else:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(png_path, 'PNG', optimize=True)
    
    def _post_process_png(self, png_path: str):
        """Post-process PNG file including transparency check and moving."""
        try:
            # Process transparent images
            png_path = self.process_transparent_image(png_path)
            
            # Wait for file to be fully written
            time.sleep(0.1)
            
            # Handle PNG file (renaming and moving)
            if os.path.exists(png_path) and os.path.getsize(png_path) > 0:
                self.handle_png_file(png_path)
            else:
                logging.warning(f'PNG file was not created properly: {png_path}')
                
        except Exception as e:
            logging.error(f'Error post-processing PNG file {png_path}: {e}')
    
    def _cleanup_exr_file(self, exr_path: str):
        """Clean up original EXR file."""
        try:
            os.remove(exr_path)
            logging.info(f'Deleted original EXR file: {exr_path}')
        except Exception as e:
            logging.warning(f'Failed to delete original EXR file {exr_path}: {e}')
    
    def process_transparent_image(self, png_path: str) -> str:
        """Check if image is entirely transparent and crop to 2x2 if needed."""
        try:
            with Image.open(png_path) as img:
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                alpha_channel = img.split()[-1]
                alpha_array = np.array(alpha_channel)
                
                if np.all(alpha_array == 0):
                    logging.info(f"Detected entirely transparent image: {png_path}, cropping to 2x2")
                    cropped_img = Image.new('RGBA', (2, 2), (0, 0, 0, 0))
                    cropped_img.save(png_path, 'PNG')
                    logging.info(f"Successfully cropped transparent image to 2x2: {png_path}")
                    
        except Exception as e:
            logging.error(f"Error checking/processing transparency for {png_path}: {e}")
        
        return png_path
    
    def handle_png_file(self, png_path: str):
        """Handle PNG files with enhanced stability checks and error handling."""
        try:
            # Enhanced stability check
            if not self._wait_for_file_stability(png_path, max_wait=10):
                logging.debug(f"PNG file not stable or missing: {png_path}")
                return
            
            directory = os.path.dirname(png_path)
            filename = os.path.basename(png_path)
            name, ext = os.path.splitext(filename)
            
            # Remove suffixes
            new_name = name
            if new_name.endswith('-Beauty'):
                new_name = new_name[:-7]
            if new_name.endswith('-gearCanvas'):
                new_name = new_name[:-11]
            
            # Rename if necessary
            if new_name != name:
                new_filename = new_name + ext
                new_path = os.path.join(directory, new_filename)
                
                if not os.path.exists(png_path):
                    logging.debug(f"PNG file disappeared before rename: {png_path}")
                    return
                
                try:
                    os.rename(png_path, new_path)
                    logging.info(f"Renamed: {filename} → {new_filename}")
                    png_path = new_path
                except (OSError, FileNotFoundError) as e:
                    logging.warning(f"Failed to rename PNG file {png_path}: {e}")
                    return
            
            # Move to final output directory
            final_path = self._move_to_final_directory(png_path)
            
            # Notify UI of new image after successful processing
            if final_path:
                self._notify_image_update(final_path)
            
        except Exception as e:
            logging.error(f"Error handling PNG file {png_path}: {e}")
    
    def _move_to_final_directory(self, png_path: str) -> str:
        """Move PNG file to final output directory. Returns final path if successful."""
        if not self.final_output_directory or not os.path.exists(self.final_output_directory):
            if not self.final_output_directory:
                logging.warning(f"Final output directory not set, PNG remains: {png_path}")
            else:
                logging.warning(f"Final output directory does not exist: {self.final_output_directory}")
            return png_path  # Return original path if can't move
        
        if not os.path.exists(png_path):
            logging.debug(f"PNG file disappeared before move: {png_path}")
            return None
        
        final_png_path = os.path.join(self.final_output_directory, os.path.basename(png_path))
        
        try:
            shutil.move(png_path, final_png_path)
            logging.info(f"Moved PNG to final output: {png_path} → {final_png_path}")
            return final_png_path
        except (OSError, FileNotFoundError, shutil.Error) as e:
            logging.warning(f"Failed to move PNG file from {png_path} to {final_png_path}: {e}")
            return png_path  # Return original path if move failed
    
    def get_conversion_stats(self) -> dict:
        """Get conversion statistics."""
        return self.conversion_stats.copy()
    
    def reset_stats(self):
        """Reset conversion statistics."""
        self.conversion_stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
        self.processed_files.clear()


# ============================================================================
# ENHANCED CLEANUP MANAGER
# ============================================================================
class CleanupManager:
    def __init__(self):
        self.temp_files = []
        self.image_references = []
        self.executor = None
        self.cleanup_registered = False
        self.save_settings_callback = None
        self.settings_saved_on_close = False
        self.browser_driver = None
        self.file_observer = None
        self.exr_handler = None
    
    def register_temp_file(self, filepath):
        """Register a temporary file for cleanup"""
        self.temp_files.append(filepath)
    
    def register_image_reference(self, image_ref):
        """Register an image reference for cleanup"""
        self.image_references.append(image_ref)
    
    def register_executor(self, executor):
        """Register a thread pool executor for cleanup"""
        self.executor = executor
    
    def register_browser_driver(self, driver):
        """Register a browser driver for cleanup"""
        self.browser_driver = driver
    
    def register_settings_callback(self, callback):
        """Register a callback to save settings on exit"""
        self.save_settings_callback = callback
    
    def mark_settings_saved(self):
        """Mark that settings have been saved to prevent duplicate saves"""
        self.settings_saved_on_close = True
    
    def start_file_monitoring(self, server_output_dir, final_output_dir, image_update_callback=None):
        """Start monitoring the server output directory for new .exr files"""
        try:
            if self.file_observer is not None:
                self.stop_file_monitoring()
            
            if not os.path.exists(server_output_dir):
                os.makedirs(server_output_dir, exist_ok=True)
            
            if not os.path.exists(final_output_dir):
                os.makedirs(final_output_dir, exist_ok=True)
            
            self.exr_handler = ExrFileHandler(final_output_dir)
            
            # Set up the image update callback for UI notifications
            if image_update_callback:
                self.exr_handler.set_image_update_callback(image_update_callback)
            
            self.file_observer = Observer()
            self.file_observer.schedule(self.exr_handler, server_output_dir, recursive=True)
            # Also monitor the final output directory for any direct image additions
            self.file_observer.schedule(self.exr_handler, final_output_dir, recursive=True)
            self.file_observer.start()
            logging.info(f'Started file monitoring for .exr files in server output: {server_output_dir}')
            logging.info(f'Processed PNGs will be moved to final output: {final_output_dir}')
        except Exception as e:
            logging.error(f'Failed to start file monitoring: {e}')
    
    def stop_file_monitoring(self):
        """Stop monitoring files and clean up the observer"""
        try:
            if self.file_observer is not None:
                self.file_observer.stop()
                self.file_observer.join(timeout=5.0)  # Wait up to 5 seconds
                self.file_observer = None
                logging.info('Stopped file monitoring')
            
            if self.exr_handler is not None:
                self.exr_handler.stop_conversion_thread()
                self.exr_handler = None
                logging.info('Stopped EXR conversion handler')
        except Exception as e:
            logging.error(f'Error stopping file monitoring: {e}')
    
    def stop_iray_server(self):
        """Stop all iray_server.exe and iray_server_worker.exe processes"""
        killed_processes = []
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name']
                    if proc_name and any(name.lower() in proc_name.lower() for name in ['iray_server.exe', 'iray_server_worker.exe']):
                        proc.kill()
                        killed_processes.append(proc_name)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if killed_processes:
                logging.info(f'Stopped Iray Server processes: {", ".join(killed_processes)}')
        except Exception as e:
            logging.error(f'Failed to stop Iray Server processes: {e}')
    
    def cleanup_all(self):
        """Clean up all registered resources"""
        try:
            # Stop file monitoring first
            self.stop_file_monitoring()
            
            # Close browser driver if exists
            if self.browser_driver:
                try:
                    self.browser_driver.quit()
                    logging.info('Browser driver closed via cleanup manager')
                except Exception as e:
                    error_msg = str(e)
                    if "connection broken" in error_msg.lower() or "connection refused" in error_msg.lower():
                        logging.info('Browser driver was already closed or unreachable')
                    else:
                        logging.warning(f'Error during browser driver cleanup (non-critical): {e}')
                finally:
                    self.browser_driver = None
            
            # Stop Iray Server processes
            self.stop_iray_server()
            
            # Only save settings if callback is available, widgets are still valid, and settings haven't been saved already
            if self.save_settings_callback and not self.settings_saved_on_close:
                try:
                    self.save_settings_callback()
                except (tk.TclError, Exception) as e:
                    # Widgets may have been destroyed already, this is normal during shutdown
                    logging.debug(f"Could not save settings during cleanup (widgets may be destroyed): {e}")
            
            # Clear image references first
            for img_ref in self.image_references:
                try:
                    if hasattr(img_ref, 'close'):
                        img_ref.close()
                    del img_ref
                except Exception:
                    pass
            self.image_references.clear()
            
            # Force garbage collection
            gc.collect()
            
            # Shutdown executor if exists
            if self.executor:
                try:
                    self.executor.shutdown(wait=False)
                except Exception:
                    pass
            
            # Clean up temporary files
            for temp_file in self.temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception:
                    pass
            self.temp_files.clear()
            
            # Additional cleanup for PIL temporary files
            try:
                # Clear PIL's internal cache
                Image._initialized = 0
                # Force cleanup of any remaining temporary files
                temp_dir = tempfile.gettempdir()
                for filename in os.listdir(temp_dir):
                    if filename.startswith('tmp') and ('PIL' in filename or 'Tk' in filename):
                        try:
                            temp_path = os.path.join(temp_dir, filename)
                            if os.path.isfile(temp_path):
                                os.unlink(temp_path)
                        except Exception:
                            pass
            except Exception:
                pass
            
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

cleanup_manager = CleanupManager()

def register_cleanup():
    """Register cleanup function to be called on exit"""
    if not cleanup_manager.cleanup_registered:
        atexit.register(cleanup_manager.cleanup_all)
        cleanup_manager.cleanup_registered = True

def archive_and_delete(inner_path, archive_path):
    logging.info(f"Archiving {inner_path} to {archive_path}")
    try:
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
            for root, dirs, files in os.walk(inner_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, inner_path)
                    zipf.write(file_path, arcname)
        logging.info(f"Successfully archived {inner_path} to {archive_path}")
        try:
            shutil.rmtree(inner_path)
            logging.info(f"Deleted folder {inner_path}")
        except Exception as e:
            logging.error(f"Failed to delete folder {inner_path}: {e}")
    except Exception as e:
        logging.error(f"Failed to archive {inner_path}: {e}")

def archive_all_inner_folders(base_path):
    """Archive all inner folders in the structure base_path/*/*/* to zip, then delete the folder."""
    to_archive = []
    for folder_name in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder_name)
        if os.path.isdir(folder_path):
            for subfolder_name in os.listdir(folder_path):
                subfolder_path = os.path.join(folder_path, subfolder_name)
                if os.path.isdir(subfolder_path):
                    for inner_name in os.listdir(subfolder_path):
                        inner_path = os.path.join(subfolder_path, inner_name)
                        if os.path.isdir(inner_path):
                            archive_path = os.path.join(subfolder_path, f"{inner_name}.zip")
                            if not os.path.exists(archive_path):
                                to_archive.append((inner_path, archive_path))
    max_workers = min(int(os.environ.get('DEFAULT_MAX_WORKERS', DEFAULT_MAX_WORKERS)), os.cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        cleanup_manager.register_executor(executor)
        futures = [executor.submit(archive_and_delete, inner_path, archive_path) for inner_path, archive_path in to_archive]
        for future in as_completed(futures):
            try:
                future.result()  # Ensure any exceptions are raised here
            except Exception as e:
                logging.error(f"An error occurred while processing a future: {e}")

def format_file_size(size_bytes):
    """Format file size in bytes to human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        # When running from source, images are in the parent directory
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def setup_logger():
    # Try to write log to %APPDATA%/Overlord/log.txt (user-writable)
    log_dir = get_app_data_path()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'log.txt')
    from logging.handlers import RotatingFileHandler
    max_bytes = LOG_SIZE_MB * 1024 * 1024  # Convert MB to bytes
    file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=1, encoding='utf-8')
    stream_handler = logging.StreamHandler()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[file_handler, stream_handler]
    )
    logging.info(f'--- Overlord started --- (log file: {log_path}, max size: {LOG_SIZE_MB} MB)')

def check_process_running(process_names):
    """Check if any processes with the given names are running"""
    try:
        for proc in psutil.process_iter(['name']):
            try:
                proc_name = proc.info['name']
                if proc_name and any(name.lower() in proc_name.lower() for name in process_names):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return False

def is_iray_server_running():
    """Check if Iray Server processes are already running"""
    return check_process_running(['iray_server.exe', 'iray_server_worker.exe'])

def start_iray_server():
    """Start the Iray Server if it's not already running"""
    if is_iray_server_running():
        logging.info('Iray Server already running, skipping startup')
        return
    
    try:
        # Clean up iray_server.db and cache folder from both possible locations
        cleanup_locations = []
        
        # Add source directory
        cleanup_locations.append(os.path.dirname(__file__))
        
        # Add LocalAppData directory if different
        local_app_data_dir = get_local_app_data_path()
        if local_app_data_dir != os.path.dirname(__file__):
            cleanup_locations.append(local_app_data_dir)
        
        for cleanup_dir in cleanup_locations:
            # Clean up iray_server.db
            iray_db_path = os.path.join(cleanup_dir, "iray_server.db")
            if os.path.exists(iray_db_path):
                os.remove(iray_db_path)
                logging.info(f"Cleaned up iray_server.db at: {iray_db_path}")
            
            # Clean up cache folder
            cache_dir_path = os.path.join(cleanup_dir, "cache")
            if os.path.exists(cache_dir_path):
                shutil.rmtree(cache_dir_path)
                logging.info(f"Cleaned up cache folder at: {cache_dir_path}")
        
        # Reference and execute runIrayServer.vbs from correct location
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller executable - look in LocalAppData
            vbs_dir = os.path.join(get_local_app_data_path(), 'scripts')
            vbs_path = os.path.join(vbs_dir, 'runIrayServer.vbs')
            # Set working directory to LocalAppData/Overlord so Iray Server can create files there
            working_dir = get_local_app_data_path()
            
            # Ensure the directories exist (backup safety check)
            if not os.path.exists(vbs_dir):
                try:
                    os.makedirs(vbs_dir, exist_ok=True)
                    logging.info(f"Created directory: {vbs_dir}")
                except Exception as e:
                    logging.error(f"Failed to create directory {vbs_dir}: {e}")
                    return
            
            if not os.path.exists(working_dir):
                try:
                    os.makedirs(working_dir, exist_ok=True)
                except Exception as e:
                    logging.error(f"Failed to create working directory {working_dir}: {e}")
                    return
        else:
            # Running from source
            vbs_path = os.path.join(os.path.dirname(__file__), "runIrayServer.vbs")
            # Set working directory to the source directory for development
            working_dir = os.path.dirname(__file__)
        
        if not os.path.exists(vbs_path):
            logging.error(f"runIrayServer.vbs not found: {vbs_path}")
            return
            
        # Use subprocess instead of os.startfile to control working directory
        subprocess.Popen(['cscript', '//NoLogo', vbs_path], cwd=working_dir, 
                       creationflags=subprocess.CREATE_NO_WINDOW)
        logging.info(f"Iray Server started automatically from working directory: {working_dir}")
    except Exception as e:
        logging.error(f"Failed to start Iray Server automatically: {e}")

# open_iray_server_web_interface function is now provided by iray_server_actions module

def create_splash_screen():
    """Create and show splash screen during startup"""
    splash = tk.Tk()
    splash.title("Overlord")
    splash.overrideredirect(True)  # Remove window decorations
    
    # Center the splash screen
    splash_width = 400
    splash_height = 400  # Changed from 300 to 400 to match image dimensions
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width - splash_width) // 2
    y = (screen_height - splash_height) // 2
    splash.geometry(f"{splash_width}x{splash_height}+{x}+{y}")
    
    try:
        # Load splash screen image
        splash_image = tk.PhotoImage(file=resource_path(os.path.join("images", "splashScreen.png")))
        splash_label = tk.Label(splash, image=splash_image)
        splash_label.image = splash_image  # Keep reference
        splash_label.pack(fill="both", expand=True)
    except Exception as e:
        # Fallback to text if image fails to load
        logging.warning(f"Could not load splash screen image: {e}")
        splash_label = tk.Label(splash, text=f"Overlord {overlord_version}\nRender Pipeline Manager\n\nStarting up...", 
                               font=("Arial", 16), bg="#2c2c2c", fg="white")
        splash_label.pack(fill="both", expand=True)
    
    # Add status text
    status_label = tk.Label(splash, text="Starting Overlord...", font=("Arial", 10), 
                           bg="#2c2c2c", fg="white")
    status_label.pack(side="bottom", pady=10)
    
    splash.update()
    return splash, status_label

def main():
    def update_estimated_time_remaining(images_remaining):
        # Get user profile directory
        user_profile = os.environ.get('USERPROFILE') or os.path.expanduser('~')
        base_log_dir = os.path.join(user_profile, "AppData", "Roaming", "DAZ 3D")
        avg_times = []
        num_instances_str = value_entries.get("Number of Instances", None)
        try:
            num_instances = int(num_instances_str.get()) if num_instances_str else 1
        except Exception:
            num_instances = 1

        for i in range(1, num_instances + 1):
            # Always use Studio4 [i] for all instances, including i==1
            studio_dir = os.path.join(base_log_dir, f"Studio4 [{i}]")
            log_path = os.path.join(studio_dir, "log.txt")
            if not os.path.exists(log_path):
                continue
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    # Collect all matching times in this log
                    times = [float(m.group(1)) for line in f if (m := re.search(r"Total Rendering Time: (\d+(?:\.\d+)?) seconds", line))]
                    avg_times.extend(times)
            except Exception:
                continue

        # Use only the 25 most recent render times (from all logs combined)
        if avg_times and len(avg_times) > 0:
            recent_times = avg_times[-RECENT_RENDER_TIMES_LIMIT:] if len(avg_times) > RECENT_RENDER_TIMES_LIMIT else avg_times
            avg_time = sum(recent_times) / len(recent_times)
            total_seconds = int(avg_time * images_remaining)
            # Format as H:MM:SS
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if hours > 0:
                formatted = f"Estimated time remaining: {hours}:{minutes:02}:{seconds:02}"
            else:
                formatted = f"Estimated time remaining: {minutes}:{seconds:02}"
            estimated_time_remaining_var.set(formatted)
            # Set estimated completion at
            completion_time = datetime.datetime.now() + datetime.timedelta(seconds=total_seconds)
            # Format: "Thursday, July 10th, 2025 2:35 PM"
            def ordinal(n):
                if 10 <= n % 100 <= 20:
                    suffix = 'th'
                else:
                    suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
                return str(n) + suffix

            weekday = completion_time.strftime('%A')
            month = completion_time.strftime('%B')
            day = ordinal(completion_time.day)
            year = completion_time.year
            hour = completion_time.strftime('%I').lstrip('0') or '12'
            minute = completion_time.strftime('%M')
            ampm = completion_time.strftime('%p')
            completion_str = f"Estimated completion at: {weekday}, {month} {day}, {year} {hour}:{minute} {ampm}"
            estimated_completion_at_var.set(completion_str)
        else:
            estimated_time_remaining_var.set("Estimated time remaining: --")
            estimated_completion_at_var.set("Estimated completion at: --")
    
    # Show splash screen first
    splash, status_label = create_splash_screen()
    status_label.config(text="Setting up logger...")
    splash.update()
    
    setup_logger()
    register_cleanup()  # Register cleanup functions
    
    status_label.config(text="Loading application...")
    splash.update()
    
    # Give browser a moment to open
    time.sleep(1)
    
    # Close splash screen
    splash.destroy()
    
    logging.info('Application launched')
    logging.info(f'Windows theme detected: {theme_manager.current_theme} mode')
    # Create the main window
    root = tk.Tk()
    root.title(f"Overlord {overlord_version}")
    root.iconbitmap(resource_path(os.path.join("images", "favicon.ico")))  # Set the application icon
    
    # Apply theme to root window
    theme_manager.register_widget(root, "root")
    # Setup ttk styles early
    theme_manager.setup_ttk_style()
    
    # Register proper window close handler
    def on_closing():
        """Handle window closing event"""
        logging.info('Application closing...')
        # Save settings before cleanup to avoid accessing destroyed widgets
        try:
            save_current_settings()
            cleanup_manager.mark_settings_saved()  # Mark that settings have been saved
        except Exception as e:
            logging.error(f"Error saving settings before close: {e}")
        kill_render_related_processes()
        cleanup_manager.cleanup_all()
        root.quit()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Maximize the application window
    root.state("zoomed")

    # Load and display the logo image
    logo = tk.PhotoImage(file=resource_path(os.path.join("images", "overlordLogo.png")))
    logo_label = tk.Label(root, image=logo, cursor="hand2")
    logo_label.image = logo  # Keep a reference to avoid garbage collection
    logo_label.place(anchor="nw", x=10, y=10)  # Place in upper left corner, 10px down and right
    theme_manager.register_widget(logo_label, "label")

    # Add Laserwolve Games logo to upper right corner
    lwg_logo = tk.PhotoImage(file=resource_path(os.path.join("images", "laserwolveGamesLogo.png")))
    lwg_logo_label = tk.Label(root, image=lwg_logo, cursor="hand2")
    lwg_logo_label.image = lwg_logo  # Keep a reference to avoid garbage collection
    # Place in upper right using place geometry manager
    lwg_logo_label.place(anchor="nw", x=700)
    theme_manager.register_widget(lwg_logo_label, "label")
    def open_lwg_link(event):
        logging.info('Laserwolve Games logo clicked')
        webbrowser.open("https://www.laserwolvegames.com/")
    lwg_logo_label.bind("<Button-1>", open_lwg_link)

    def open_github_link(event):
        logging.info('Overlord GitHub logo clicked')
        webbrowser.open("https://github.com/Laserwolve-Games/Overlord")
    logo_label.bind("<Button-1>", open_github_link)

    # Create frames for the two tables
    file_table_frame = tk.Frame(root)
    file_table_frame.pack(pady=(150, 10), anchor="nw", side="top")  # Add top padding to move down
    theme_manager.register_widget(file_table_frame, "frame")
    
    param_table_frame = tk.Frame(root)
    param_table_frame.pack(pady=(20, 10), anchor="nw", side="top")  # 20px down from file_table_frame
    theme_manager.register_widget(param_table_frame, "frame")

    # File/folder path parameters
    file_params = [
        "Source Files",
        "Output Directory"
    ]
    # Short/simple parameters
    param_params = [
        "Number of Instances",
        "Frame Rate",
        "Log File Size (MBs)"
    ]
    value_entries = {}

    # Replace file_table_frame headers with a centered "Options" header
    options_header = tk.Label(file_table_frame, text="Options", font=("Arial", 14, "bold"))
    options_header.grid(row=0, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
    theme_manager.register_widget(options_header, "label")
    file_table_frame.grid_columnconfigure(0, weight=1)
    file_table_frame.grid_columnconfigure(1, weight=1)
    file_table_frame.grid_columnconfigure(2, weight=1)

    def make_browse_file(entry, initialdir=None, filetypes=None, title="Select file"):
        def browse_file():
            filename = filedialog.askopenfilename(
                initialdir=initialdir or "",
                title=title,
                filetypes=filetypes or (("All files", "*.*"),)
            )
            if filename:
                entry.delete(0, tk.END)
                entry.insert(0, filename)
        return browse_file

    def make_browse_folder(entry, initialdir=None, title="Select folder"):
        def browse_folder():
            foldername = filedialog.askdirectory(
                initialdir=initialdir or "",
                title=title
            )
            if foldername:
                entry.delete(0, tk.END)
                entry.insert(0, foldername)
        return browse_folder

    def make_browse_files(text_widget, initialdir=None, filetypes=None, title="Select files"):
        def browse_files():
            filenames = filedialog.askopenfilenames(
                initialdir=initialdir or "",
                title=title,
                filetypes=filetypes or (("All files", "*.*"),)
            )
            if filenames:
                text_widget.delete("1.0", tk.END)
                text_widget.insert(tk.END, "\n".join(filenames))
        return browse_files

    # Auto-save settings when important values change
    def auto_save_settings(*args):
        try:
            save_current_settings()
        except Exception as e:
            logging.error(f"Auto-save settings failed: {e}")

    # File/folder path parameters table
    for i, param in enumerate(file_params):
        param_label = tk.Label(file_table_frame, text=param, font=("Arial", 10), anchor="w")
        param_label.grid(row=i+1, column=0, padx=10, pady=5, sticky="w")
        theme_manager.register_widget(param_label, "label")

        if param == "Source Files":
            text_widget = tk.Text(file_table_frame, width=80, height=5, font=("Consolas", 10))
            text_widget.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            theme_manager.register_widget(text_widget, "text")
            def browse_files_append():
                # Start in user's Documents directory
                documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
                filenames = filedialog.askopenfilenames(
                    initialdir=documents_dir,
                    title="Select Source Files",
                    filetypes=(("DSON User File", "*.duf"),)
                )
                if filenames:
                    filenames = [fname.replace('/', '\\') for fname in filenames]
                    current = text_widget.get("1.0", tk.END).strip().replace('/', '\\')
                    current_files = set(current.split("\n")) if current else set()
                    new_files = [fname for fname in filenames if fname not in current_files]
                    if new_files:
                        # If textbox is not empty, append new files each on a new line
                        if current:
                            text_widget.insert(tk.END, "\n" + "\n".join(new_files))
                        else:
                            text_widget.insert(tk.END, "\n".join(new_files))
            button_frame = tk.Frame(file_table_frame)
            button_frame.grid(row=i+1, column=2, padx=5, pady=5, sticky="n")
            theme_manager.register_widget(button_frame, "frame")

            browse_button = tk.Button(
                button_frame,
                text="Browse",
                command=browse_files_append,
                width=8
            )
            browse_button.pack(side="top", fill="x", pady=(0, 2))
            theme_manager.register_widget(browse_button, "button")

            def clear_source_files():
                text_widget.delete("1.0", tk.END)
            clear_button = tk.Button(
                button_frame,
                text="Clear",
                command=clear_source_files,
                width=8
            )
            clear_button.pack(side="top", fill="x")
            theme_manager.register_widget(clear_button, "button")
            value_entries[param] = text_widget
            
            # Bind auto-save for source files (save after a delay to avoid saving on every keystroke)
            def schedule_source_files_save(event=None):
                # Cancel any existing scheduled save
                if hasattr(schedule_source_files_save, 'after_id'):
                    root.after_cancel(schedule_source_files_save.after_id)
                # Schedule save after 2 seconds of inactivity
                schedule_source_files_save.after_id = root.after(AUTO_SAVE_DELAY, auto_save_settings)
            
            text_widget.bind("<KeyRelease>", schedule_source_files_save)
            text_widget.bind("<FocusOut>", lambda e: auto_save_settings())
        elif param == "Output Directory":
            value_entry = tk.Entry(file_table_frame, width=80, font=("Consolas", 10))
            default_img_dir = os.path.join(
                os.path.expanduser("~"),
                "Downloads", "output"
            )
            value_entry.insert(0, default_img_dir)
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            theme_manager.register_widget(value_entry, "entry")

            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=make_browse_folder(
                    value_entry,
                    initialdir=default_img_dir,
                    title="Select Output Directory"
                ),
                width=8
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            theme_manager.register_widget(browse_button, "button")
            value_entries[param] = value_entry




    # Short/simple parameters table
    for i, param in enumerate(param_params):
        param_label = tk.Label(param_table_frame, text=param, font=("Arial", 10), anchor="w")
        param_label.grid(row=i+1, column=0, padx=10, pady=5, sticky="w")
        theme_manager.register_widget(param_label, "label")

        value_entry = tk.Entry(param_table_frame, width=5, font=("Consolas", 10))
        if param == "Number of Instances":
            value_entry.insert(0, "1")
        elif param == "Log File Size (MBs)":
            value_entry.insert(0, "100")
        elif param == "Frame Rate":
            value_entry.insert(0, "30")
        value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
        theme_manager.register_widget(value_entry, "entry")
        value_entries[param] = value_entry

    # --- Only keep Render Shadows checkbox ---
    render_shadows_var = tk.BooleanVar(value=True)
    render_shadows_label = tk.Label(param_table_frame, text="Render shadows", font=("Arial", 10), anchor="w")
    render_shadows_label.grid(row=len(param_params)+1, column=0, padx=10, pady=(0, 0), sticky="w")
    theme_manager.register_widget(render_shadows_label, "label")
    render_shadows_checkbox = tk.Checkbutton(
        param_table_frame,
        variable=render_shadows_var,
        width=2,
        anchor="w"
    )
    render_shadows_checkbox.grid(row=len(param_params)+1, column=1, padx=10, pady=(0, 5), sticky="w")
    theme_manager.register_widget(render_shadows_checkbox, "checkbutton")

    # Register settings save callback for cleanup
    def save_current_settings():
        current_settings = settings_manager.get_current_settings(value_entries, render_shadows_var)
        settings_manager.save_settings(current_settings)
    cleanup_manager.register_settings_callback(save_current_settings)

    saved_settings = settings_manager.load_settings()
    # Apply the loaded settings to the UI (now that all widgets are created)
    settings_manager.apply_settings(saved_settings, value_entries, render_shadows_var)

    # Log settings loading - settings loaded silently
    
    # Bind auto-save to key widgets
    value_entries["Output Directory"].bind("<FocusOut>", lambda e: auto_save_settings())
    value_entries["Number of Instances"].bind("<FocusOut>", lambda e: auto_save_settings())
    value_entries["Frame Rate"].bind("<FocusOut>", lambda e: auto_save_settings())
    value_entries["Log File Size (MBs)"].bind("<FocusOut>", lambda e: auto_save_settings())
    
    # For checkboxes, bind to the variable change
    render_shadows_var.trace_add('write', auto_save_settings)

    # --- Last Rendered Image Section ---
    right_frame = tk.Frame(root)
    right_frame.place(relx=0.73, rely=0.0, anchor="n", width=1024, height=1024)
    theme_manager.register_widget(right_frame, "frame")

    # Set border color based on theme
    border_color = "#cccccc" if theme_manager.current_theme == "light" else "#555555"
    right_frame.config(highlightbackground=border_color, highlightthickness=1)

    # Place img_label directly in right_frame
    img_label = tk.Label(right_frame)
    img_label.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)
    theme_manager.register_widget(img_label, "label")

    # --- Image Details Column ---
    # Place details_frame to the right of param_table_frame
    details_frame = tk.Frame(root, width=350)
    details_frame.place(relx=0.25, rely=0.6, anchor="nw", width=350, height=200)
    details_frame.pack_propagate(False)
    theme_manager.register_widget(details_frame, "frame")

    details_title = tk.Label(details_frame, text="Last Rendered Image Details", font=("Arial", 14, "bold"))
    details_title.pack(anchor="nw", pady=(0, 10))
    theme_manager.register_widget(details_title, "label")

    # Show only the path (no "Path: " prefix)
    details_path = tk.Label(details_frame, text="", font=("Consolas", 9), wraplength=330, justify="left")
    details_path.pack(anchor="nw", pady=(0, 5))
    theme_manager.register_widget(details_path, "label")

    # Add a button to copy the path to clipboard
    def copy_path_to_clipboard():
        path = details_path.cget("text")
        if path:
            root.clipboard_clear()
            root.clipboard_append(path)
            root.update()  # Keeps clipboard after window closes

    copy_btn = tk.Button(details_frame, text="Copy Path", command=copy_path_to_clipboard, font=("Arial", 9))
    copy_btn.pack(anchor="nw", pady=(0, 8))
    theme_manager.register_widget(copy_btn, "button")

    details_size = tk.Label(details_frame, text="Size: ", font=("Arial", 10))
    details_size.pack(anchor="nw", pady=(0, 5))
    theme_manager.register_widget(details_size, "label")
    details_dim = tk.Label(details_frame, text="Dimensions: ", font=("Arial", 10))
    details_dim.pack(anchor="nw", pady=(0, 5))
    theme_manager.register_widget(details_dim, "label")


    # --- Output Details Column ---
    output_details_frame = tk.Frame(root, width=350)
    output_details_frame.place(relx=0.01, rely=0.6, anchor="nw", width=350, height=200)
    output_details_frame.pack_propagate(False)
    theme_manager.register_widget(output_details_frame, "frame")

    # Progress Bar for Render Completion (directly above Output Details title, not inside output_details_frame)
    from tkinter import ttk
    progress_var = tk.DoubleVar(master=root, value=0)
    # Label for images remaining (above progress bar)
    images_remaining_var = tk.StringVar(master=root, value="Images remaining: --")
    estimated_time_remaining_var = tk.StringVar(master=root, value="Estimated time remaining: --")
    estimated_completion_at_var = tk.StringVar(master=root, value="Estimated completion at: --")
    images_remaining_label = tk.Label(
        root,
        textvariable=images_remaining_var,
        font=("Arial", 10, "bold"),
        anchor="w",
        justify="left"
    )
    theme_manager.register_widget(images_remaining_label, "label")
    estimated_time_remaining_label = tk.Label(
        root,
        textvariable=estimated_time_remaining_var,
        font=("Arial", 10, "bold"),
        anchor="e",
        justify="center"
    )
    theme_manager.register_widget(estimated_time_remaining_label, "label")
    estimated_completion_at_label = tk.Label(
        root,
        textvariable=estimated_completion_at_var,
        font=("Arial", 10, "bold"),
        anchor="e",
        justify="right"
    )
    theme_manager.register_widget(estimated_completion_at_label, "label")
    images_remaining_label.place(relx=0.01, rely=0.55, anchor="nw", width=250, height=18)
    theme_manager.register_widget(images_remaining_label, "label")
    estimated_time_remaining_label.place(relx=0.11, rely=0.55, anchor="nw", width=250, height=18)
    theme_manager.register_widget(estimated_time_remaining_label, "label")
    estimated_completion_at_label.place(relx=0.245, rely=0.55, anchor="nw", width=400, height=18)
    theme_manager.register_widget(estimated_completion_at_label, "label")

    progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100)
    # Place the progress bar just above the output_details_frame, matching its width and alignment
    progress_bar.place(relx=0.01, rely=0.57, anchor="nw", width=850, height=18)
    theme_manager.register_widget(progress_bar, "progressbar")

    output_details_title = tk.Label(output_details_frame, text="Output Details", font=("Arial", 14, "bold"))
    output_details_title.pack(anchor="nw", pady=(0, 10))
    theme_manager.register_widget(output_details_title, "label")

    output_folder_size = tk.Label(output_details_frame, text="Folder Size: ", font=("Arial", 10))
    output_folder_size.pack(anchor="nw", pady=(0, 5))
    theme_manager.register_widget(output_folder_size, "label")
    output_png_count = tk.Label(output_details_frame, text="PNG Files: ", font=("Arial", 10))
    output_png_count.pack(anchor="nw", pady=(0, 5))
    theme_manager.register_widget(output_png_count, "label")
    output_zip_count = tk.Label(output_details_frame, text="ZIP Files: ", font=("Arial", 10))
    output_zip_count.pack(anchor="nw", pady=(0, 5))
    theme_manager.register_widget(output_zip_count, "label")

    output_folder_count = tk.Label(output_details_frame, text="Sub-folders: ", font=("Arial", 10))
    output_folder_count.pack(anchor="nw", pady=(0, 5))
    theme_manager.register_widget(output_folder_count, "label")

    # Add Total Images to Render label (updated only on Start Render)
    output_total_images = tk.Label(output_details_frame, text="Total Images to Render: ", font=("Arial", 10))
    theme_manager.register_widget(output_total_images, "label")
    # output_total_images.pack(anchor="nw", pady=(0, 5))

    def update_output_details():
        """Update the output details with current folder statistics"""
        output_dir = value_entries["Output Directory"].get()
        if not os.path.exists(output_dir):
            output_folder_size.config(text="Folder Size: N/A")
            output_png_count.config(text="PNG Files: N/A")
            output_zip_count.config(text="ZIP Files: N/A")
            output_folder_count.config(text="Sub-folders: N/A")
            progress_var.set(0)
            images_remaining_var.set("Images remaining: --")
            return
        try:
            total_size = 0
            png_count = 0
            zip_count = 0
            folder_count = 0
            for rootdir, dirs, files in os.walk(output_dir):
                for dir_name in dirs:
                    folder_count += 1
                for file in files:
                    file_path = os.path.join(rootdir, file)
                    try:
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        if file.lower().endswith('.png'):
                            png_count += 1
                        elif file.lower().endswith('.zip'):
                            zip_count += 1
                    except (OSError, IOError):
                        continue
            
            size_str = format_file_size(total_size)
            output_folder_size.config(text=f"Folder Size: {size_str}")
            output_png_count.config(text=f"PNG Files: {png_count}")
            output_zip_count.config(text=f"ZIP Files: {zip_count}")
            output_folder_count.config(text=f"Sub-folders: {folder_count}")
            # Update progress bar and images remaining label
            try:
                total_images_str = output_total_images.cget("text").replace("Total Images to Render: ", "").strip()
                if not total_images_str:
                    progress_var.set(0)
                    images_remaining_var.set("Images remaining: --")
                    estimated_time_remaining_var.set("Estimated time remaining: --")
                    estimated_completion_at_var.set("Estimated completion at: --")
                    return
                total_images = int(total_images_str) if total_images_str.isdigit() else None
                if total_images and total_images > 0:
                    percent = min(100, (png_count / total_images) * 100)
                    progress_var.set(percent)
                    remaining = max(0, total_images - png_count)
                    images_remaining_var.set(f"Images remaining: {remaining}")
                    update_estimated_time_remaining(remaining)
                else:
                    progress_var.set(0)
                    images_remaining_var.set("Images remaining: --")
                    estimated_time_remaining_var.set("Estimated time remaining: --")
                    estimated_completion_at_var.set("Estimated completion at: --")
            except Exception:
                progress_var.set(0)
                images_remaining_var.set("Images remaining: --")
                estimated_time_remaining_var.set("Estimated time remaining: --")
                estimated_completion_at_var.set("Estimated completion at: --")
        except Exception as e:
            output_folder_size.config(text="Folder Size: Error")
            output_png_count.config(text="PNG Files: Error")
            output_zip_count.config(text="ZIP Files: Error")
            output_folder_count.config(text="Sub-folders: Error")
            progress_var.set(0)
            images_remaining_var.set("Images remaining: --")

    no_img_label = tk.Label(right_frame, text="No images found in output directory", font=("Arial", 12))
    no_img_label.place(relx=0.5, rely=0.5, anchor="center")
    no_img_label.lower()  # Hide initially
    theme_manager.register_widget(no_img_label, "label")

    def find_newest_image(directory):
        image_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
        # Collect all image files and their modification times
        image_files = []
        for rootdir, _, files in os.walk(directory):
            for fname in files:
                if fname.lower().endswith(image_exts):
                    fpath = os.path.join(rootdir, fname)
                    try:
                        mtime = os.path.getmtime(fpath)
                        image_files.append((mtime, fpath))
                    except Exception:
                        continue
        # Sort by most recent first
        image_files.sort(reverse=True)
        return [fpath for mtime, fpath in image_files]

    def show_last_rendered_image():
        """Display the most recent image from the output directory."""
        output_dir = value_entries["Output Directory"].get()
        image_paths = find_newest_image(output_dir)
        displayed = False
        for newest_img_path in image_paths:
            if not os.path.exists(newest_img_path):
                continue
            try:
                # Clean up previous image reference if it exists
                if hasattr(img_label, 'image') and img_label.image:
                    try:
                        old_img = img_label.image
                        if hasattr(old_img, 'close'):
                            old_img.close()
                        del old_img
                    except Exception:
                        pass
                
                # First, verify the image integrity
                with Image.open(newest_img_path) as verify_img:
                    verify_img.verify()  # Will raise if the image is incomplete or corrupt
                
                # If verification passes, reopen for display
                with Image.open(newest_img_path) as img:
                    img = img.convert("RGBA")  # Ensure image is in RGBA mode
                    # Handle transparency by adding a theme-appropriate background
                    if theme_manager.current_theme == "dark":
                        # Dark grey background for dark theme
                        bg_color = (60, 60, 60, 255)  # Dark grey
                    else:
                        # White background for light theme
                        bg_color = (255, 255, 255, 255)  # White
                    bg = Image.new("RGBA", img.size, bg_color)
                    img = Image.alpha_composite(bg, img)
                    
                    # Create a copy to avoid keeping the file handle open
                    img_copy = img.copy()
                    width, height = img.size
                
                with Image.open(newest_img_path) as orig_img:
                    width, height = orig_img.size
                
                file_size = os.path.getsize(newest_img_path)
                # Always display path with Windows separators
                details_path.config(text=newest_img_path.replace('/', '\\'))  # No "Path: " prefix
                details_dim.config(text=f"Dimensions: {width} x {height}")
                details_size.config(text=f"Size: {file_size/1024:.1f} KB")
                
                tk_img = ImageTk.PhotoImage(img_copy)
                cleanup_manager.register_image_reference(tk_img)  # Register for cleanup
                img_label.config(image=tk_img)
                img_label.image = tk_img
                no_img_label.lower()
                
                # Only log if the image path has changed
                if getattr(show_last_rendered_image, 'last_logged_img_path', None) != newest_img_path:
                    logging.info(f'Displaying image: {newest_img_path}')
                    show_last_rendered_image.last_logged_img_path = newest_img_path
                show_last_rendered_image.last_no_img_logged = False
                displayed = True
                break
            except Exception:
                continue
        
        if not displayed:
            # Clean up image reference
            if hasattr(img_label, 'image') and img_label.image:
                try:
                    old_img = img_label.image
                    if hasattr(old_img, 'close'):
                        old_img.close()
                    del old_img
                except Exception:
                    pass
            
            img_label.config(image="")
            img_label.image = None
            details_path.config(text="")
            details_dim.config(text="Dimensions: ")
            details_size.config(text="Size: ")
            no_img_label.lift()
            if not getattr(show_last_rendered_image, 'last_no_img_logged', False):
                logging.info('No images found in output directory or all images failed to load')
                show_last_rendered_image.last_no_img_logged = True
        
        # Force garbage collection to clean up any remaining references
        gc.collect()

    def watchdog_image_update(new_image_path):
        """Called by watchdog when a new image is detected. Schedules UI update on main thread."""
        def update_ui():
            try:
                output_dir = value_entries["Output Directory"].get()
                # Only update if the new image is in the current output directory
                if os.path.dirname(new_image_path) == output_dir or new_image_path.startswith(output_dir):
                    show_last_rendered_image()
                    logging.debug(f'UI updated for new image: {new_image_path}')
            except Exception as e:
                logging.error(f'Error updating UI for new image {new_image_path}: {e}')
        
        # Schedule the update on the main thread
        try:
            root.after(100, update_ui)  # Small delay to ensure file is fully written
        except Exception as e:
            logging.error(f'Error scheduling UI update for new image: {e}')

    def periodic_update_output_details():
        """Periodically update output details every 5 seconds"""
        update_output_details()
        root.after(OUTPUT_UPDATE_INTERVAL, periodic_update_output_details)

    # Update image when output directory changes or after render
    def on_output_dir_change(*args):
        new_output_dir = value_entries["Output Directory"].get()
        logging.info(f'Output Directory changed to: {new_output_dir}')
        
        # Update the final output directory in the ExrFileHandler if it exists
        if hasattr(cleanup_manager, 'exr_handler') and cleanup_manager.exr_handler is not None:
            cleanup_manager.exr_handler.set_final_output_directory(new_output_dir)
            logging.info(f'Updated ExrFileHandler final output directory to: {new_output_dir}')
        
        # Restart file monitoring to include the new output directory
        if hasattr(cleanup_manager, 'file_observer') and cleanup_manager.file_observer is not None:
            try:
                server_output_dir = get_server_output_directory()
                cleanup_manager.start_file_monitoring(server_output_dir, new_output_dir, watchdog_image_update)
                logging.info(f'Restarted file monitoring for new output directory: {new_output_dir}')
            except Exception as e:
                logging.error(f'Failed to restart file monitoring: {e}')
        
        root.after(200, show_last_rendered_image)
        root.after(200, update_output_details)
    value_entries["Output Directory"].bind("<FocusOut>", lambda e: on_output_dir_change())
    value_entries["Output Directory"].bind("<Return>", lambda e: on_output_dir_change())

    def start_render():
        # Prevent multiple render starts
        if button.cget("state") == "disabled":
            logging.info("Start Render already in progress, ignoring additional click")
            return

        # Validate Source Files and Output Directory before launching render
        source_files = value_entries["Source Files"].get("1.0", tk.END).strip().replace("\\", "/").split("\n")
        source_files = [file for file in source_files if file]
        output_dir = value_entries["Output Directory"].get().strip()
        if not source_files:
            from tkinter import messagebox
            messagebox.showerror("Missing Source Files", "Please specify at least one Source File before starting the render.")
            logging.info("Start Render cancelled: No Source Files specified.")
            return
        if not output_dir:
            from tkinter import messagebox
            messagebox.showerror("Missing Output Directory", "Please specify an Output Directory before starting the render.")
            logging.info("Start Render cancelled: No Output Directory specified.")
            return
        
        # Disable Start Render button and enable Stop Render button
        button.config(state="disabled")
        stop_button.config(state="normal")
        root.update_idletasks()  # Force UI update
        
        # Start the render process in a background thread to keep UI responsive
        def start_render_background():
            try:
                # Start Iray Server if not already running
                logging.info('Start Render button clicked')
                logging.info('Starting Iray Server...')
                
                # Get server output directory path
                server_output_dir = get_server_output_directory()
                
                # delete iray_server.db and cache folder
                script_dir = os.path.dirname(os.path.abspath(__file__))
                iray_db_path = os.path.join(script_dir, "iray_server.db")
                cache_dir_path = os.path.join(script_dir, "cache")
            
                if os.path.exists(iray_db_path):
                    os.remove(iray_db_path)
                    logging.info(f"Successfully deleted iray_server.db at: {iray_db_path}")
                else:
                    logging.info(f"iray_server.db not found at: {iray_db_path} (nothing to delete)")
                
                if os.path.exists(cache_dir_path):
                    shutil.rmtree(cache_dir_path)
                    logging.info(f"Successfully deleted cache folder at: {cache_dir_path}")
                else:
                    logging.info(f"cache folder not found at: {cache_dir_path} (nothing to delete)")

                # Clean up server output directory to start fresh
                if os.path.exists(server_output_dir):
                    shutil.rmtree(server_output_dir)
                    logging.info(f"Successfully deleted server output folder at: {server_output_dir}")
                os.makedirs(server_output_dir, exist_ok=True)
                logging.info(f"Created fresh server output directory at: {server_output_dir}")

                
                start_iray_server()  # Start Iray Server
                
                # Wait for Iray server to start up (in background thread, so it won't block UI)
                time.sleep(IRAY_STARTUP_DELAY / 1000)  # Convert to seconds
                
                # Use intermediate server output directory for Iray Server configuration
                
                iray_actions = IrayServerActions(cleanup_manager)
                
                # Configure Iray Server (starts browser, configures settings, closes browser)
                if not iray_actions.configure_server(server_output_dir):
                    logging.error('Failed to configure Iray Server')
                    # Shutdown Iray Server since configuration failed
                    cleanup_manager.stop_iray_server()
                    raise Exception("Iray Server configuration failed")
                
                logging.info('Iray Server configuration complete')
                
                # Continue with the rest of the render setup on UI thread
                root.after(0, continue_render_setup)
                
            except Exception as e:
                logging.error(f"Failed to start render: {e}")
                # Re-enable Start Render button and disable Stop Render button on error
                root.after(0, lambda: (button.config(state="normal"), stop_button.config(state="disabled")))
        
        def continue_render_setup():
            try:
                # Continue with rest of render setup
                complete_render_setup()
                
            except Exception as e:
                logging.error(f"Failed to continue render setup: {e}")
                # Re-enable Start Render button and disable Stop Render button on error
                button.config(state="normal")
                stop_button.config(state="disabled")
        
        # Start the background process
        render_thread = threading.Thread(target=start_render_background, daemon=True)
        render_thread.start()
        
    def complete_render_setup():
        # Get source files again (since we're in a different scope now)
        source_files = value_entries["Source Files"].get("1.0", tk.END).strip().replace("\\", "/").split("\n")
        source_files = [file for file in source_files if file]
        
        # Calculate and display total images to render (update label)
        def find_total_images(source_files):
            total_frames = 0
            for file_path in source_files:
                if '_animation.duf' in file_path:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            json_start = content.find('{')
                            if json_start == -1:
                                continue
                            data = json.loads(content[json_start:])
                            animations = data.get('scene', {}).get('animations', [])
                            for anim in animations:
                                keys = anim.get('keys', [])
                                if len(keys) != 1:
                                    total_frames += len(keys)
                                    break
                    except Exception:
                        continue
            return total_frames

        total_images = None
        try:
            if source_files:
                total_images = find_total_images(source_files)
        except Exception:
            total_images = None
        if total_images is not None:
            # TODO: This should be read from the JSON of the _subject files.
            total_images *= 16
            # If Render Shadows is checked, double the total images
            if render_shadows_var.get():
                total_images *= 2
            output_total_images.config(text=f"Total Images to Render: {total_images}")
        else:
            output_total_images.config(text="Total Images to Render: ")

        # Check if any DAZ Studio instances are running
        daz_running = check_process_running(['DAZStudio'])

        # Show confirmation dialog if DAZ Studio is running
        if daz_running:
            from tkinter import messagebox
            result = messagebox.askyesno(
                "DAZ Studio Running", 
                "DAZ Studio is already running.\n\nDo you want to continue?",
                icon="warning"
            )
            if not result:
                logging.info('Start Render cancelled by user - DAZ Studio running')
                # Re-enable Start Render button and disable Stop Render button
                button.config(state="normal")
                stop_button.config(state="disabled")
                return

        # Update button to show launching state
        root.update_idletasks()

        # Hardcoded Daz Studio Executable Path
        daz_executable_path = os.path.join(
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            "DAZ 3D", "DAZStudio4", "DAZStudio.exe"
        )
        # Use local scripts directory if running in VS Code (not frozen), else use user-writable scripts directory
        if getattr(sys, 'frozen', False):
            install_dir = os.path.dirname(sys.executable)
            user_scripts_dir = os.path.join(get_app_data_path(), 'scripts')
            os.makedirs(user_scripts_dir, exist_ok=True)
            render_script_path = os.path.join(user_scripts_dir, "masterRenderer.dsa").replace("\\", "/")
            install_script_path = os.path.join(install_dir, "scripts", "masterRenderer.dsa")
            try:
                if (not os.path.exists(render_script_path)) or (
                    os.path.getmtime(install_script_path) > os.path.getmtime(render_script_path)):
                    import shutil
                    shutil.copy2(install_script_path, render_script_path)
                    logging.info(f'Copied masterRenderer.dsa to user scripts dir: {render_script_path}')
            except Exception as e:
                logging.error(f'Could not copy masterRenderer.dsa to user scripts dir: {e}')
            # Path to masterTemplate.duf in appData
            template_path = os.path.join(get_app_data_path(), 'templates', 'masterTemplate.duf').replace("\\", "/")
        else:
            # Use scripts directly from the repository for development/VS Code preview
            install_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            render_script_path = os.path.join(install_dir, "scripts", "masterRenderer.dsa").replace("\\", "/")
            template_path = os.path.join(install_dir, "templates", "masterTemplate.duf").replace("\\", "/")
        # Use "Source Files" and treat as files
        source_files_json = json.dumps(source_files)
        image_output_dir = value_entries["Output Directory"].get().replace("\\", "/")
        num_instances = value_entries["Number of Instances"].get()
        log_size = value_entries["Log File Size (MBs)"].get()
        log_size = int(log_size) * 1000000  # Convert MBs to bytes
        frame_rate = value_entries["Frame Rate"].get()

        try:
            num_instances_int = int(num_instances)
        except Exception:
            num_instances_int = 1

        # Add render_shadows to json_map
        render_shadows = render_shadows_var.get()
        json_map = (
            f'{{'
            f'"num_instances": "{num_instances}", '
            f'"image_output_dir": "{image_output_dir}", '
            f'"frame_rate": "{frame_rate}", '
            f'"source_files": {source_files_json}, '
            f'"template_path": "{template_path}", '
            f'"render_shadows": {str(render_shadows).lower()}'
            f'}}'
        )

        def run_instance():
            logging.info('Launching Daz Studio render instance')
            command = [
                daz_executable_path,
                "-scriptArg", json_map,
                "-instanceName", "#",
                "-logSize", str(log_size),
                "-headless",
                "-noPrompt", 
                render_script_path
            ]
            logging.info(f'Command executed: {command}')
            try:
                subprocess.Popen(command)
                logging.info('Daz Studio instance started successfully')
            except Exception as e:
                logging.error(f'Failed to start Daz Studio instance: {e}')
                
        def run_all_instances(i=0):
            if i < num_instances_int:
                run_instance()
                root.after(DAZ_STUDIO_STARTUP_DELAY, lambda: run_all_instances(i + 1))
            else:
                logging.info('All render instances launched')
                # Start file monitoring for .exr files in server output directory, move processed PNGs to final output
                server_output_dir = get_server_output_directory()
                cleanup_manager.start_file_monitoring(server_output_dir, image_output_dir, watchdog_image_update)
                root.after(IMAGE_UPDATE_INTERVAL, show_last_rendered_image)  # Update image after render

        run_all_instances()
        # If "Close Overlord After Starting Render" is checked, close after 2 seconds
        # (Removed: if close_after_render_var.get(): ...)
        # (Removed: any use of close_after_render_var or close_daz_on_finish_var)

    def kill_render_related_processes():
        """Kill all Daz Studio, Iray Server, and webdriver/browser processes. Also resets UI progress labels."""
        logging.info('Killing all render-related processes (DAZStudio, Iray Server, webdriver/browsers)')
        # Stop file monitoring first
        cleanup_manager.stop_file_monitoring()
        killed_daz = 0
        killed_webdriver = 0
        try:
            # Kill all DAZStudio processes
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and 'DAZStudio' in proc.info['name']:
                        proc.kill()
                        killed_daz += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            # Kill Iray Server processes using cleanup manager
            cleanup_manager.stop_iray_server()
            # Kill only webdriver processes (not regular browsers)
            webdriver_names = [
                'geckodriver'
            ]
            for proc in psutil.process_iter(['name']):
                try:
                    pname = proc.info['name']
                    if pname and any(wd in pname.lower() for wd in webdriver_names):
                        proc.kill()
                        killed_webdriver += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            main.dazstudio_killed_by_user = True
            logging.info(f'Killed {killed_daz} DAZStudio, {killed_webdriver} webdriver process(es). Iray Server stopped via cleanup manager.')
        except Exception as e:
            logging.error(f'Failed to stop render processes: {e}')
        # Reset progress and time labels, and total images label (always reset regardless of error)
        output_total_images.config(text="Total Images to Render: ")
        images_remaining_var.set("Images remaining: --")
        estimated_time_remaining_var.set("Estimated time remaining: --")
        estimated_completion_at_var.set("Estimated completion at: --")
        progress_var.set(0)

    def stop_render():
        logging.info('Stop Render button clicked')
        # Stop file monitoring first
        cleanup_manager.stop_file_monitoring()
        kill_render_related_processes()
        # Re-enable Start Render button and disable Stop Render button
        button.config(state="normal")
        stop_button.config(state="disabled")

    # Initial display setup
    root.after(500, show_last_rendered_image)  # Initial image load
    root.after(OUTPUT_UPDATE_INTERVAL, periodic_update_output_details)  # Start periodic output updates

    # --- Buttons Section ---
    buttons_frame = tk.Frame(root)
    buttons_frame.place(relx=0.0, rely=0.78, anchor="nw")
    theme_manager.register_widget(buttons_frame, "frame")

    button = tk.Button(buttons_frame, text="Start Render", command=start_render, font=("Arial", 16, "bold"), width=16, height=2)
    button.pack(side="left", padx=(20, 10), pady=10)
    theme_manager.register_widget(button, "button")

    stop_button = tk.Button(
        buttons_frame,
        text="Stop Render",
        command=stop_render,
        font=("Arial", 16, "bold"),
        width=26,
        height=2,
        state="disabled"  # Initially disabled until Start Render is clicked
    )
    stop_button.pack(side="left", padx=10, pady=10)
    theme_manager.register_widget(stop_button, "button")

    def zip_outputted_files():
        logging.info('Zip Outputted Files button clicked')
        
        # Check if any DAZ Studio instances are running
        daz_running = check_process_running(['DAZStudio'])
        
        # Show confirmation dialog if DAZ Studio is running
        if daz_running:
            from tkinter import messagebox
            result = messagebox.askyesno(
                "DAZ Studio Running", 
                "DAZ Studio is currently running. Archiving while rendering may cause issues.\n\nDo you want to continue anyway?",
                icon="warning"
            )
            if not result:
                logging.info('Archive cancelled by user - DAZ Studio running')
                return
        
        try:
            output_dir = value_entries["Output Directory"].get()
            archive_all_inner_folders(output_dir)
            logging.info(f'Archiving completed for: {output_dir}')
        except Exception as e:
            logging.error(f'Failed to archive output files: {e}')

    zip_button = tk.Button(
        buttons_frame,
        text="Zip Outputted Files",
        command=zip_outputted_files,
        font=("Arial", 16, "bold"),
        width=18,
        height=2
    )
    zip_button.pack(side="left", padx=10, pady=10)
    theme_manager.register_widget(zip_button, "button")

    # Run the application
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logging.info('Application interrupted by user')
    finally:
        # Ensure cleanup happens even if mainloop exits abnormally
        cleanup_manager.cleanup_all()
        logging.info('Application cleanup completed')

if __name__ == "__main__":
    main()
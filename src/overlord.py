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
import time
import threading
import glob
import argparse
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
from tkinter import messagebox
import winreg
import psutil
import atexit
import tempfile
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from version import __version__ as overlord_version

def get_display_version() -> str:
    """Get the display version string. Shows 'dev' when running in development mode."""
    try:
        # If sys._MEIPASS exists, we're running from a PyInstaller executable (production)
        sys._MEIPASS
        return overlord_version
    except AttributeError:
        # Running from source (development mode)
        return "dev"

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

# Application constants
DEFAULT_MAX_WORKERS = 8
LOG_SIZE_MB = 100
RENDERS_PER_SESSION = 100
RECENT_RENDER_TIMES_LIMIT = 25

# UI update intervals (milliseconds)
AUTO_SAVE_DELAY = 2000

# Process startup delays (milliseconds)
DAZ_STUDIO_STARTUP_DELAY = 5000
OVERLORD_CLOSE_DELAY = 2000
IRAY_STARTUP_DELAY = 10000

# File extensions
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
SCENE_EXTENSIONS = ('.duf',)

# Default paths
DEFAULT_OUTPUT_SUBDIR = "Downloads/output"
APPDATA_SUBFOLDER = "Overlord"

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

# Error messages
ERROR_MESSAGES = {
    "missing_subject": "Please specify a Subject file before starting the render.",
    "missing_animation": "Please specify at least one animation before starting the render.",
    "missing_output_dir": "Please specify an Output Directory before starting the render.",
    "daz_running_warning": "DAZ Studio is already running.\n\nDo you want to continue?",
    "iray_config_failed": "Iray Server configuration failed",
    "render_start_failed": "Failed to start render",
    "file_not_found": "File Validation Error",
    "invalid_file_extension": "Invalid File Extension",
}

# Validation limits
VALIDATION_LIMITS = {
    "max_instances": 16, "min_instances": 1, "max_frame_rate": 120, "min_frame_rate": 1,
    "max_file_wait_time": 10, "png_stability_wait": 3,
}

# UI text constants
UI_TEXT = {
    "app_title": "Overlord", "options_header": "Options", "last_image_details": "Last Rendered Image Details",
    "output_details": "Output Details", "copy_path": "Copy Path", "start_render": "Start Render",
    "stop_render": "Stop Render", "browse": "Browse", "clear": "Clear",
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
    """Get directory statistics: total_size, png_count, folder_count."""
    if not os.path.exists(directory):
        return 0, 0, 0
    
    total_size = png_count = folder_count = 0
    
    for rootdir, dirs, files in os.walk(directory):
        folder_count += len(dirs)
        for file in files:
            file_path = os.path.join(rootdir, file)
            try:
                file_size = os.path.getsize(file_path)
                total_size += file_size
                if file.lower().endswith('.png'):
                    png_count += 1
            except (OSError, IOError):
                continue
    
    return total_size, png_count, folder_count

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
    logging.info('Stopping all render-related processes (DAZStudio, Iray Server)')
    
    results = {
        'daz_studio': kill_processes_by_name(DAZ_STUDIO_PROCESSES),
        'iray_server': stop_iray_server(),
    }
    
    total = sum(results.values())
    logging.info(f'Stopped {total} total process(es): '
                f'{results["daz_studio"]} DAZ Studio, '
                f'{results["iray_server"]} Iray Server')
    
    return results

def cleanup_iray_files_in_directory(cleanup_dir, with_retries=True):
    """Clean up all Iray-related files and folders in a specific directory."""
    items_cleaned = []
    
    # Files and folders to clean up
    cleanup_items = [
        ("iray_server.db", "file"),
        ("cache", "folder"),
        ("preview", "folder"),
        ("results", "folder"),
        ("iray_server.log", "file")
    ]
    
    # Clean up standard items
    for item_name, item_type in cleanup_items:
        item_path = os.path.join(cleanup_dir, item_name)
        if os.path.exists(item_path):
            try:
                if with_retries and item_type in ["file", "folder"]:
                    # Try to delete with retries (processes might still be releasing file handles)
                    max_retries = 5
                    retry_delay = 0.5  # seconds
                    for attempt in range(max_retries):
                        try:
                            if item_type == "file":
                                os.remove(item_path)
                            elif item_type == "folder":
                                shutil.rmtree(item_path)
                            items_cleaned.append(f"{item_type}: {item_path}")
                            logging.info(f"Cleaned up {item_type} at: {item_path}")
                            break
                        except (OSError, PermissionError) as e:
                            if attempt < max_retries - 1:
                                logging.debug(f"Attempt {attempt + 1} failed to delete {item_path}, retrying in {retry_delay}s: {e}")
                                time.sleep(retry_delay)
                            else:
                                logging.warning(f"Failed to delete {item_type} after {max_retries} attempts: {e}")
                else:
                    # Simple deletion without retries
                    if item_type == "file":
                        os.remove(item_path)
                    elif item_type == "folder":
                        shutil.rmtree(item_path)
                    items_cleaned.append(f"{item_type}: {item_path}")
                    logging.info(f"Cleaned up {item_type} at: {item_path}")
            except Exception as e:
                logging.warning(f"Failed to delete {item_type} at {item_path}: {e}")
    
    # Clean up worker log files (worker_*.log)
    try:
        worker_log_pattern = os.path.join(cleanup_dir, "worker_*.log")
        worker_log_files = glob.glob(worker_log_pattern)
        for worker_log_file in worker_log_files:
            try:
                if with_retries:
                    # Try to delete with retries
                    max_retries = 5
                    retry_delay = 0.5  # seconds
                    for attempt in range(max_retries):
                        try:
                            os.remove(worker_log_file)
                            items_cleaned.append(f"worker log: {worker_log_file}")
                            logging.info(f"Cleaned up worker log file at: {worker_log_file}")
                            break
                        except (OSError, PermissionError) as e:
                            if attempt < max_retries - 1:
                                logging.debug(f"Attempt {attempt + 1} failed to delete {worker_log_file}, retrying in {retry_delay}s: {e}")
                                time.sleep(retry_delay)
                            else:
                                logging.warning(f"Failed to delete worker log file after {max_retries} attempts: {e}")
                else:
                    # Simple deletion without retries
                    os.remove(worker_log_file)
                    items_cleaned.append(f"worker log: {worker_log_file}")
                    logging.info(f"Cleaned up worker log file at: {worker_log_file}")
            except Exception as e:
                logging.warning(f"Failed to delete worker log file at {worker_log_file}: {e}")
    except Exception as e:
        logging.warning(f"Error finding worker log files in {cleanup_dir}: {e}")
    
    return items_cleaned

def cleanup_iray_database_and_cache():
    """Clean up all Iray-related files and folders from all possible locations."""
    try:
        cleanup_locations = []
        all_cleaned_items = []
        
        # Add source directory
        cleanup_locations.append(os.path.dirname(__file__))
        
        # Add LocalAppData directory if different
        local_app_data_dir = get_local_app_data_path()
        if local_app_data_dir != os.path.dirname(__file__):
            cleanup_locations.append(local_app_data_dir)
        
        for cleanup_dir in cleanup_locations:
            logging.info(f"Cleaning up Iray files in directory: {cleanup_dir}")
            cleaned_items = cleanup_iray_files_in_directory(cleanup_dir, with_retries=True)
            all_cleaned_items.extend(cleaned_items)
        
        if all_cleaned_items:
            logging.info(f"Total cleanup completed: {len(all_cleaned_items)} items cleaned")
        else:
            logging.info("No Iray files found to clean up")
                
    except Exception as e:
        logging.error(f"Error during comprehensive Iray cleanup: {e}")


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
            time.sleep(0.05)
            if not os.path.exists(file_path):
                return False
            size2 = os.path.getsize(file_path)
            if size1 == size2 and size1 > 0:
                return True
        except (OSError, FileNotFoundError):
            return False
        time.sleep(0.2)
        wait_time += 0.25
    return False

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
                bg_color = (60, 60, 60, 255)  # Dark background
            else:
                bg_color = (255, 255, 255, 255)  # Light background
            
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
        splash_label = tk.Label(splash, text=f"Overlord {get_display_version()}\nRender Pipeline Manager\n\nStarting up...", 
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

class ThemeManager:
    """Enhanced theme management with better organization and features."""
    
    def __init__(self):
        self.current_theme = detect_windows_theme()
        self.themes = THEME_COLORS
        self.widgets_to_theme = []
        self.ttk_style = None
        self.theme_change_callbacks = []  # List of callbacks to call when theme changes
        
    def add_theme_change_callback(self, callback):
        """Add a callback function to be called when the theme changes."""
        self.theme_change_callbacks.append(callback)
        
    def _call_theme_change_callbacks(self):
        """Call all registered theme change callbacks."""
        for callback in self.theme_change_callbacks:
            try:
                callback()
            except Exception as e:
                logging.error(f"Error calling theme change callback: {e}")
        
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
            elif widget_type == "canvas":
                widget.configure(bg=self.get_color("bg"), highlightbackground=self.get_color("border"))
            elif widget_type == "scrollbar":
                widget.configure(bg=self.get_color("button_bg"), 
                               troughcolor=self.get_color("entry_bg"),
                               activebackground=self.get_color("highlight_bg"))
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
        self._call_theme_change_callbacks()  # Call registered callbacks
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
    def validate_animations(files: list) -> bool:
        """Validate animations list."""
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
            "subject": "",
            "animations": [],
            "prop_animations": [],
            "gear": [],
            "gear_animations": [],
            "output_directory": get_default_output_directory(),
            "number_of_instances": "1",
            "frame_rate": "30",
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
        
        return issues
    
    def get_current_settings(self, value_entries: dict, render_shadows_var) -> dict:
        """Extract current settings from UI widgets."""
        try:
            animations_text = value_entries["Animations"].get("1.0", tk.END).strip()
            animations = [f.strip() for f in animations_text.split('\n') if f.strip()]
            
            prop_animations_text = value_entries["Prop Animations"].get("1.0", tk.END).strip()
            prop_animations = [f.strip() for f in prop_animations_text.split('\n') if f.strip()]
            
            gear_text = value_entries["Gear"].get("1.0", tk.END).strip()
            gear = [f.strip() for f in gear_text.split('\n') if f.strip()]
            
            gear_animations_text = value_entries["Gear Animations"].get("1.0", tk.END).strip()
            gear_animations = [f.strip() for f in gear_animations_text.split('\n') if f.strip()]
            
            return {
                "subject": value_entries["Subject"].get(),
                "animations": animations,
                "prop_animations": prop_animations,
                "gear": gear,
                "gear_animations": gear_animations,
                "output_directory": value_entries["Output Directory"].get(),
                "number_of_instances": value_entries["Number of Instances"].get(),
                "frame_rate": value_entries["Frame Rate"].get(),
                "render_shadows": render_shadows_var.get()
            }
        except tk.TclError:
            # Widgets have been destroyed, return default settings
            logging.warning("Widgets destroyed during settings extraction, using defaults")
            return self.default_settings.copy()
    
    def apply_settings(self, settings: dict, value_entries: dict, render_shadows_var) -> bool:
        """Apply loaded settings to UI widgets."""
        try:
            # Subject
            value_entries["Subject"].delete(0, tk.END)
            value_entries["Subject"].insert(0, settings["subject"])
            
            # Animations (text widget)
            value_entries["Animations"].delete("1.0", tk.END)
            if settings["animations"]:
                value_entries["Animations"].insert("1.0", "\n".join(settings["animations"]))
            
            # Prop Animations (text widget)
            value_entries["Prop Animations"].delete("1.0", tk.END)
            if settings["prop_animations"]:
                value_entries["Prop Animations"].insert("1.0", "\n".join(settings["prop_animations"]))
            
            # Gear (text widget)
            value_entries["Gear"].delete("1.0", tk.END)
            if settings["gear"]:
                value_entries["Gear"].insert("1.0", "\n".join(settings["gear"]))
            
            # Gear Animations (text widget)
            value_entries["Gear Animations"].delete("1.0", tk.END)
            if settings["gear_animations"]:
                value_entries["Gear Animations"].insert("1.0", "\n".join(settings["gear_animations"]))
            
            # Output Directory
            value_entries["Output Directory"].delete(0, tk.END)
            value_entries["Output Directory"].insert(0, settings["output_directory"])
            
            # Number of Instances
            value_entries["Number of Instances"].delete(0, tk.END)
            value_entries["Number of Instances"].insert(0, settings["number_of_instances"])
            
            # Frame Rate
            value_entries["Frame Rate"].delete(0, tk.END)
            value_entries["Frame Rate"].insert(0, settings["frame_rate"])
            
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
        # Remove file monitoring functionality
    
    def register_temp_file(self, filepath):
        """Register a temporary file for cleanup"""
        self.temp_files.append(filepath)
    
    def register_image_reference(self, image_ref):
        """Register an image reference for cleanup"""
        self.image_references.append(image_ref)
    
    def register_executor(self, executor):
        """Register a thread pool executor for cleanup"""
        self.executor = executor
    
    def register_settings_callback(self, callback):
        """Register a callback to save settings on exit"""
        self.save_settings_callback = callback
    
    def mark_settings_saved(self):
        """Mark that settings have been saved to prevent duplicate saves"""
        self.settings_saved_on_close = True
    
    def stop_file_monitoring(self):
        """Stop file monitoring (no-op since file monitoring was removed)"""
        # This method is called by various parts of the code but does nothing
        # since we removed all file monitoring functionality
        pass
    
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
        return True
    
    try:
        # Clean up all Iray-related files from both possible locations
        cleanup_locations = []
        
        # Add source directory
        cleanup_locations.append(os.path.dirname(__file__))
        
        # Add LocalAppData directory if different
        local_app_data_dir = get_local_app_data_path()
        if local_app_data_dir != os.path.dirname(__file__):
            cleanup_locations.append(local_app_data_dir)
        
        for cleanup_dir in cleanup_locations:
            logging.info(f"Cleaning up Iray files in directory before server start: {cleanup_dir}")
            cleanup_iray_files_in_directory(cleanup_dir, with_retries=False)  # No retries for faster startup
        
        # Launch Iray Server directly using Python subprocess
        iray_server_exe = r"C:\Program Files\NVIDIA Corporation\Iray Server\server\iray_server.exe"
        iray_install_path = r"C:\Program Files\NVIDIA Corporation\Iray Server"
        
        # Set working directory based on execution context
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller executable - use LocalAppData
            working_dir = get_local_app_data_path()
        else:
            # Running from source - use source directory
            working_dir = os.path.dirname(__file__)
        
        # Ensure working directory exists
        if not os.path.exists(working_dir):
            try:
                os.makedirs(working_dir, exist_ok=True)
                logging.info(f"Created working directory: {working_dir}")
            except Exception as e:
                logging.error(f"Failed to create working directory {working_dir}: {e}")
                return False
        
        # Check if Iray Server executable exists
        if not os.path.exists(iray_server_exe):
            logging.error(f"Iray Server executable not found: {iray_server_exe}")
            return False
        
        # Build command arguments
        cmd = [
            iray_server_exe,
            '--install-path', iray_install_path,
            '--start-queue'
        ]
        
        # Launch Iray Server directly without creating a visible window
        try:
            # Use SW_HIDE flag through creationflags to keep the process hidden
            subprocess.Popen(
                cmd, 
                cwd=working_dir, 
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            logging.info(f"Iray Server started from working directory: {working_dir} using direct executable: {iray_server_exe}")
        except Exception as e:
            logging.error(f"Failed to launch Iray Server executable {iray_server_exe}: {e}")
            return False
        
        # Wait for the server to actually start up and become accessible
        import socket
        max_wait_time = 30  # Wait up to 30 seconds for server to start
        wait_interval = 1  # Check every 1 second
        
        for attempt in range(max_wait_time):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('127.0.0.1', 9090))
                sock.close()
                
                if result == 0:
                    logging.info(f"Iray Server is now accessible on port 9090 (took {attempt + 1} seconds)")
                    return True
            except Exception:
                pass
            
            time.sleep(wait_interval)
        
        logging.error("Iray Server failed to become accessible within 30 seconds")
        return False
        
    except Exception as e:
        logging.error(f"Failed to start Iray Server automatically: {e}")
        return False

# ============================================================================
# SINGLE INSTANCE MANAGEMENT
# ============================================================================

# Global variable to store the lock file handle
_lock_file_handle = None

def ensure_single_instance():
    """
    Ensures only one instance of Overlord can run at a time.
    Returns True if this is the only instance, False if another instance is already running.
    """
    global _lock_file_handle
    
    # Get the temporary directory for lock file
    temp_dir = tempfile.gettempdir()
    lock_file_path = os.path.join(temp_dir, "overlord_instance.lock")
    
    try:
        # Try to create/open lock file exclusively
        if os.name == 'nt':  # Windows
            import msvcrt
            try:
                # Open file in exclusive mode
                _lock_file_handle = open(lock_file_path, 'w')
                msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                
                # Write current process ID to lock file
                _lock_file_handle.write(str(os.getpid()))
                _lock_file_handle.flush()
                
                # Register cleanup function to remove lock on exit
                atexit.register(cleanup_single_instance)
                
                return True
                
            except (IOError, OSError):
                # Lock file exists and is locked by another process
                if _lock_file_handle:
                    _lock_file_handle.close()
                    _lock_file_handle = None
                
                # Check if the process that created the lock is still running
                if os.path.exists(lock_file_path):
                    try:
                        with open(lock_file_path, 'r') as f:
                            pid_str = f.read().strip()
                            if pid_str.isdigit():
                                pid = int(pid_str)
                                # Check if process is still running
                                if psutil.pid_exists(pid):
                                    try:
                                        proc = psutil.Process(pid)
                                        # Check if it's actually an Overlord process
                                        if 'overlord.py' in ' '.join(proc.cmdline()) or 'overlord' in proc.name().lower():
                                            # Show a brief notification and exit
                                            try:
                                                import tkinter as tk
                                                from tkinter import messagebox
                                                root = tk.Tk()
                                                root.withdraw()  # Hide the main window
                                                messagebox.showinfo(
                                                    "Overlord Already Running",
                                                    "Another instance of Overlord is already running.\n\nOnly one instance can run at a time."
                                                )
                                                root.destroy()
                                            except:
                                                # If GUI fails, just print to console
                                                print("Overlord is already running. Only one instance can run at a time.")
                                            return False  # Another Overlord instance is running
                                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                                        pass
                                
                                # Stale lock file, remove it and try again
                                try:
                                    os.remove(lock_file_path)
                                    return ensure_single_instance()  # Recursive call to try again
                                except OSError:
                                    pass
                    except (IOError, ValueError):
                        # Corrupted lock file, try to remove it
                        try:
                            os.remove(lock_file_path)
                            return ensure_single_instance()  # Recursive call to try again
                        except OSError:
                            pass
                
                return False
        else:
            # Unix/Linux implementation (if needed in the future)
            import fcntl
            try:
                _lock_file_handle = open(lock_file_path, 'w')
                fcntl.flock(_lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                _lock_file_handle.write(str(os.getpid()))
                _lock_file_handle.flush()
                
                atexit.register(cleanup_single_instance)
                return True
                
            except (IOError, OSError):
                if _lock_file_handle:
                    _lock_file_handle.close()
                    _lock_file_handle = None
                return False
    
    except Exception as e:
        # Fallback: if file locking fails, check running processes
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] != current_pid:
                    cmdline = proc.info['cmdline'] or []
                    if any('overlord.py' in arg for arg in cmdline) or 'overlord' in proc.info['name'].lower():
                        # Show notification before returning False
                        try:
                            import tkinter as tk
                            from tkinter import messagebox
                            root = tk.Tk()
                            root.withdraw()  # Hide the main window
                            messagebox.showinfo(
                                "Overlord Already Running",
                                "Another instance of Overlord is already running.\n\nOnly one instance can run at a time."
                            )
                            root.destroy()
                        except:
                            print("Overlord is already running. Only one instance can run at a time.")
                        return False  # Another Overlord instance found
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return True  # No other instance found

def cleanup_single_instance():
    """Clean up the lock file when the application exits."""
    global _lock_file_handle
    
    if _lock_file_handle:
        try:
            _lock_file_handle.close()
        except:
            pass
        _lock_file_handle = None
    
    # Remove lock file
    temp_dir = tempfile.gettempdir()
    lock_file_path = os.path.join(temp_dir, "overlord_instance.lock")
    try:
        if os.path.exists(lock_file_path):
            os.remove(lock_file_path)
    except OSError:
        pass

def run_headless_mode(cmd_args):
    """Run Overlord in headless mode without UI"""
    logging.info('Starting Overlord in headless mode')
    
    # Load default settings
    settings_manager = SettingsManager()
    settings = settings_manager.load_settings()
    
    # Apply command line arguments to settings
    if cmd_args:
        if cmd_args.subject:
            settings["subject"] = cmd_args.subject
        if cmd_args.animations:
            settings["animations"] = cmd_args.animations
        if cmd_args.prop_animations:
            settings["prop_animations"] = cmd_args.prop_animations
        if cmd_args.gear:
            settings["gear"] = cmd_args.gear
        if cmd_args.gear_animations:
            settings["gear_animations"] = cmd_args.gear_animations
        if cmd_args.output_dir:
            settings["output_directory"] = cmd_args.output_dir
        if cmd_args.instances:
            settings["number_of_instances"] = str(cmd_args.instances)
        if cmd_args.frame_rate:
            settings["frame_rate"] = str(cmd_args.frame_rate)
        if cmd_args.render_shadows is not None:
            settings["render_shadows"] = cmd_args.render_shadows
    
    # Validate required fields
    if not settings.get("subject"):
        logging.error("Headless mode requires --subject argument")
        return 1
    if not settings.get("animations"):
        logging.error("Headless mode requires --animations argument")
        return 1
    if not settings.get("output_directory"):
        logging.error("Headless mode requires --output-dir argument")
        return 1
    
    # Validate files exist
    subject_file = settings["subject"]
    if not os.path.isfile(subject_file):
        logging.error(f"Subject file does not exist: {subject_file}")
        return 1
    
    animations = settings["animations"] if isinstance(settings["animations"], list) else [settings["animations"]]
    for animation_file in animations:
        if not os.path.isfile(animation_file):
            logging.error(f"Animation file does not exist: {animation_file}")
            return 1
    
    # Validate file extensions
    all_files = [subject_file] + animations
    if settings.get("prop_animations"):
        prop_animations = settings["prop_animations"] if isinstance(settings["prop_animations"], list) else [settings["prop_animations"]]
        all_files.extend(prop_animations)
    if settings.get("gear"):
        gear_files = settings["gear"] if isinstance(settings["gear"], list) else [settings["gear"]]
        all_files.extend(gear_files)
    if settings.get("gear_animations"):
        gear_animations = settings["gear_animations"] if isinstance(settings["gear_animations"], list) else [settings["gear_animations"]]
        all_files.extend(gear_animations)
    
    for file_path in all_files:
        if not file_path.lower().endswith('.duf'):
            logging.error(f"File is not a .duf file: {file_path}")
            return 1
    
    logging.info("Headless mode validation passed, starting render...")
    
    try:
        # Start the render process using the same logic as the UI version
        start_headless_render(settings)
        return 0
    except Exception as e:
        logging.error(f"Headless render failed: {e}")
        return 1

def start_headless_render(settings):
    """Start the render process in headless mode"""
    logging.info('Starting headless render process')
    
    # Initialize cleanup manager
    global cleanup_manager
    cleanup_manager = CleanupManager()
    
    # Stop any existing processes
    logging.info('Closing any existing Iray Server and DAZ Studio instances...')
    
    # Kill processes manually for headless mode
    import psutil
    killed_daz = 0
    try:
        # Kill all DAZStudio processes
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and 'DAZStudio' in proc.info['name']:
                    proc.kill()
                    killed_daz += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        logging.info(f'Killed {killed_daz} DAZStudio process(es)')
    except Exception as e:
        logging.error(f'Failed to stop DAZ processes: {e}')
    
    # Clean up Iray database and cache
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cleanup_iray_database_and_cache()
    
    # Start Iray Server
    logging.info('Starting fresh Iray Server...')
    results_dir = os.path.join(script_dir, "results")
    final_output_dir = settings["output_directory"]
    
    # Create directories
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(final_output_dir, exist_ok=True)
    
    # Start Iray Server using the global function
    if not start_iray_server():
        raise Exception("Failed to start Iray Server")
    
    logging.info('Iray Server started successfully')
    
    # Prepare render data
    subject_file = settings["subject"].replace("\\", "/")
    animations = settings["animations"] if isinstance(settings["animations"], list) else [settings["animations"]]
    animations = [anim.replace("\\", "/") for anim in animations]
    
    prop_animations = []
    if settings.get("prop_animations"):
        prop_animations = settings["prop_animations"] if isinstance(settings["prop_animations"], list) else [settings["prop_animations"]]
        prop_animations = [anim.replace("\\", "/") for anim in prop_animations]
    
    gear = []
    if settings.get("gear"):
        gear = settings["gear"] if isinstance(settings["gear"], list) else [settings["gear"]]
        gear = [g.replace("\\", "/") for g in gear]
    
    gear_animations = []
    if settings.get("gear_animations"):
        gear_animations = settings["gear_animations"] if isinstance(settings["gear_animations"], list) else [settings["gear_animations"]]
        gear_animations = [anim.replace("\\", "/") for anim in gear_animations]
    
    # Get paths using the same logic as the UI version
    daz_executable_path = os.path.join(
        os.environ.get("ProgramFiles", "C:\\Program Files"),
        "DAZ 3D", "DAZStudio4", "DAZStudio.exe"
    )
    
    # Get template and script paths
    if getattr(sys, 'frozen', False):
        install_dir = os.path.dirname(sys.executable)
        user_scripts_dir = os.path.join(get_app_data_path(), 'scripts')
        os.makedirs(user_scripts_dir, exist_ok=True)
        render_script_path = os.path.join(user_scripts_dir, "masterRenderer.dsa").replace("\\", "/")
        template_path = os.path.join(get_app_data_path(), 'templates', 'masterTemplate.duf').replace("\\", "/")
    else:
        install_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        render_script_path = os.path.join(install_dir, "scripts", "masterRenderer.dsa").replace("\\", "/")
        template_path = os.path.join(install_dir, "templates", "masterTemplate.duf").replace("\\", "/")
    
    # Create JSON map for DAZ Studio
    json_map = {
        "num_instances": str(settings.get("number_of_instances", "1")),
        "image_output_dir": final_output_dir.replace("\\", "/"),
        "frame_rate": str(settings.get("frame_rate", "30")),
        "subject_file": subject_file,
        "animations": animations,
        "prop_animations": prop_animations,
        "gear": gear,
        "gear_animations": gear_animations,
        "template_path": template_path,
        "render_shadows": settings.get("render_shadows", True),
        "results_directory_path": results_dir.replace("\\", "/")
    }
    
    # Start file monitoring
    cleanup_manager.start_file_monitoring(
        server_output_dir=results_dir,
        final_output_dir=final_output_dir
    )
    
    # Launch DAZ Studio instances
    if not os.path.exists(daz_executable_path):
        raise Exception(f"DAZ Studio executable not found: {daz_executable_path}")
    
    if not os.path.exists(render_script_path):
        raise Exception(f"Render script not found: {render_script_path}")
    
    json_map_str = json.dumps(json_map)
    
    num_instances = int(settings.get("number_of_instances", "1"))
    for i in range(num_instances):
        command = [
            daz_executable_path,
            "-scriptArg", json_map_str,
            "-instanceName", "#",
            "-logSize", "100000000",
            "-headless",
            "-noPrompt", 
            render_script_path
        ]
        
        logging.info(f"Launching DAZ Studio instance {i+1}/{num_instances}")
        subprocess.Popen(command)
        if i < num_instances - 1:  # Don't sleep after the last instance
            time.sleep(5)  # Delay between instances
    
    logging.info('All render instances launched')
    
    # In headless mode, we'll run until interrupted or completed
    try:
        # Keep the process alive and monitor progress
        while True:
            time.sleep(10)
            # You could add progress monitoring here
            # For now, just keep running until Ctrl+C
    except KeyboardInterrupt:
        logging.info('Headless render interrupted by user')
    finally:
        # Cleanup
        logging.info('Cleaning up headless render...')
        cleanup_manager.cleanup_all()

def main(auto_start_render=False, cmd_args=None, headless=False):
    def create_daz_command_array(daz_executable_path, json_map, log_size, render_script_path):
        """Create the DAZ Studio command array with all required parameters."""
        return [
            daz_executable_path,
            "-scriptArg", json_map,
            "-instanceName", "#",
            "-logSize", str(log_size),
            "-headless",
            "-noPrompt", 
            render_script_path
        ]
    
    def update_estimated_time_remaining(images_remaining):
        """Update time estimation display (simplified since EXR processing was removed)."""
        try:
            # Since we removed EXR conversion and processing, time estimation
            # is no longer meaningful - just show a simple message
            if images_remaining > 0:
                estimated_time_remaining_var.set(f"Images remaining: {images_remaining}")
                estimated_completion_at_var.set("Direct output to final directory")
            else:
                estimated_time_remaining_var.set("All images processed")
                estimated_completion_at_var.set("Render complete")
            
        except Exception as e:
            logging.error(f"Error updating status display: {e}")
            estimated_time_remaining_var.set("--")
            estimated_completion_at_var.set("--")
            estimated_completion_at_var.set("Estimated completion at: --")
    
    # Check for existing instance before showing splash screen
    if not ensure_single_instance():
        return  # Exit silently if another instance is already running
    
    # Show splash screen first
    splash, status_label = create_splash_screen()
    status_label.config(text="Setting up logger...")
    splash.update()
    
    setup_logger()
    register_cleanup()  # Register cleanup functions
    
    status_label.config(text="Loading application...")
    splash.update()
    
    time.sleep(1)
    
    # Close splash screen
    splash.destroy()
    
    # Handle headless mode
    if headless:
        return run_headless_mode(cmd_args)
    
    logging.info('Application launched')
    logging.info(f'Windows theme detected: {theme_manager.current_theme} mode')
    # Create the main window
    root = tk.Tk()
    root.title(f"Overlord {get_display_version()}")
    root.iconbitmap(resource_path(os.path.join("images", "favicon.ico")))  # Set the application icon
    
    # Apply theme to root window
    theme_manager.register_widget(root, "root")
    # Setup ttk styles early
    theme_manager.setup_ttk_style()
    
    # Register proper window close handler
    def on_closing():
        """Handle window closing event"""
        logging.info('Application closing...')
        
        # Immediately hide the window to make closing feel responsive
        root.withdraw()  # Hide the window immediately
        root.update()    # Force the UI update
        
        # Do all cleanup in a background thread
        def cleanup_background():
            try:
                # Save settings before cleanup to avoid accessing destroyed widgets
                try:
                    save_current_settings()
                    cleanup_manager.mark_settings_saved()  # Mark that settings have been saved
                    logging.info('Settings saved successfully before exit')
                except Exception as e:
                    logging.error(f"Error saving settings before close: {e}")
                
                # Kill render processes
                logging.info('Killing render-related processes...')
                kill_render_related_processes()
                
                # Full cleanup
                logging.info('Performing final cleanup...')
                cleanup_manager.cleanup_all()
                
                logging.info('Background cleanup completed')
            except Exception as e:
                logging.error(f'Error during background cleanup: {e}')
            finally:
                # Ensure the application exits
                logging.info('Exiting application...')
                import os
                os._exit(0)  # Force exit regardless of remaining threads
        
        # Start cleanup in background daemon thread
        cleanup_thread = threading.Thread(target=cleanup_background, daemon=True)
        cleanup_thread.start()
        
        # Don't call root.quit() or root.destroy() here - let the background thread handle exit
    
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Create menu bar
    def create_menu_bar():
        """Create and configure the menu bar"""
        menubar = tk.Menu(root)
        theme_manager.register_widget(menubar, "menu")
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        theme_manager.register_widget(file_menu, "menu")
        
        def choose_subject():
            """Open file picker for subject field"""
            filename = filedialog.askopenfilename(
                title="Choose Subject",
                filetypes=[("DAZ Scene Files", "*.duf"), ("All Files", "*.*")],
                initialdir=os.path.dirname(value_entries["Subject"].get()) if value_entries["Subject"].get() else None
            )
            if filename:
                value_entries["Subject"].delete(0, tk.END)
                value_entries["Subject"].insert(0, filename)
                auto_save_settings()
        
        def choose_animations():
            """Open file picker for animations field"""
            filenames = filedialog.askopenfilenames(
                title="Choose Animations",
                filetypes=[("DAZ Scene Files", "*.duf"), ("All Files", "*.*")],
                initialdir=os.path.dirname(value_entries["Animations"].get("1.0", tk.END).strip()) if value_entries["Animations"].get("1.0", tk.END).strip() else None
            )
            if filenames:
                value_entries["Animations"].delete("1.0", tk.END)
                value_entries["Animations"].insert("1.0", "\n".join(filenames))
                auto_save_settings()
        
        def choose_prop_animations():
            """Open file picker for prop animations field"""
            filenames = filedialog.askopenfilenames(
                title="Choose Prop Animations",
                filetypes=[("DAZ Scene Files", "*.duf"), ("All Files", "*.*")],
                initialdir=os.path.dirname(value_entries["Prop Animations"].get("1.0", tk.END).strip()) if value_entries["Prop Animations"].get("1.0", tk.END).strip() else None
            )
            if filenames:
                value_entries["Prop Animations"].delete("1.0", tk.END)
                value_entries["Prop Animations"].insert("1.0", "\n".join(filenames))
                auto_save_settings()
        
        def choose_gear():
            """Open file picker for gear field"""
            filenames = filedialog.askopenfilenames(
                title="Choose Gear",
                filetypes=[("DAZ Scene Files", "*.duf"), ("All Files", "*.*")],
                initialdir=os.path.dirname(value_entries["Gear"].get("1.0", tk.END).strip()) if value_entries["Gear"].get("1.0", tk.END).strip() else None
            )
            if filenames:
                value_entries["Gear"].delete("1.0", tk.END)
                value_entries["Gear"].insert("1.0", "\n".join(filenames))
                auto_save_settings()
        
        def choose_gear_animations():
            """Open file picker for gear animations field"""
            filenames = filedialog.askopenfilenames(
                title="Choose Gear Animations",
                filetypes=[("DAZ Scene Files", "*.duf"), ("All Files", "*.*")],
                initialdir=os.path.dirname(value_entries["Gear Animations"].get("1.0", tk.END).strip()) if value_entries["Gear Animations"].get("1.0", tk.END).strip() else None
            )
            if filenames:
                value_entries["Gear Animations"].delete("1.0", tk.END)
                value_entries["Gear Animations"].insert("1.0", "\n".join(filenames))
                auto_save_settings()
        
        def choose_output_directory():
            """Open folder picker for output directory field"""
            dirname = filedialog.askdirectory(
                title="Choose Output Directory",
                initialdir=value_entries["Output Directory"].get() if value_entries["Output Directory"].get() else None
            )
            if dirname:
                value_entries["Output Directory"].delete(0, tk.END)
                value_entries["Output Directory"].insert(0, dirname)
                auto_save_settings()
                on_output_dir_change()  # Update UI
        
        def exit_overlord():
            """Exit the application"""
            on_closing()
        
        file_menu.add_command(label="Choose Subject", command=choose_subject)
        file_menu.add_command(label="Choose Animations", command=choose_animations)
        file_menu.add_command(label="Choose Prop Animations", command=choose_prop_animations)
        file_menu.add_command(label="Choose Gear", command=choose_gear)
        file_menu.add_command(label="Choose Gear Animations", command=choose_gear_animations)
        file_menu.add_command(label="Choose Output Directory", command=choose_output_directory)
        file_menu.add_separator()
        file_menu.add_command(label="Exit Overlord", command=exit_overlord)
        
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        theme_manager.register_widget(edit_menu, "menu")
        
        def clear_all_input_fields():
            """Clear all input fields"""
            value_entries["Subject"].delete(0, tk.END)
            value_entries["Animations"].delete("1.0", tk.END)
            value_entries["Prop Animations"].delete("1.0", tk.END)
            value_entries["Gear"].delete("1.0", tk.END)
            value_entries["Gear Animations"].delete("1.0", tk.END)
            value_entries["Output Directory"].delete(0, tk.END)
            auto_save_settings()
            on_output_dir_change()  # Update UI
            logging.info("All input fields cleared")
        
        def restore_default_settings():
            """Restore default settings"""
            value_entries["Number of Instances"].delete(0, tk.END)
            value_entries["Number of Instances"].insert(0, "1")
            value_entries["Frame Rate"].delete(0, tk.END)
            value_entries["Frame Rate"].insert(0, "30")
            render_shadows_var.set(True)
            auto_save_settings()
            logging.info("Default settings restored")
        
        edit_menu.add_command(label="Clear All Input Fields", command=clear_all_input_fields)
        edit_menu.add_command(label="Restore Default Settings", command=restore_default_settings)
        
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        theme_manager.register_widget(help_menu, "menu")
        
        def show_overlord_log():
            """Show Overlord log with default program"""
            log_path = os.path.join(get_app_data_path(), 'log.txt')
            try:
                if os.path.exists(log_path):
                    os.startfile(log_path)  # Open with default program on Windows
                else:
                    messagebox.showinfo("Log Not Found", "Overlord log file not found.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open log file: {e}")
        
        def show_iray_server_log():
            """Show Iray Server log with default program"""
            # Look for iray_server.log in multiple locations
            possible_paths = [
                os.path.join(os.path.dirname(__file__), "iray_server.log"),
                os.path.join(get_local_app_data_path(), "iray_server.log")
            ]
            
            log_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    log_path = path
                    break
            
            if log_path:
                try:
                    os.startfile(log_path)  # Open with default program on Windows
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to open log file: {e}")
            else:
                messagebox.showinfo("Log Not Found", "Iray Server log file not found. The server may not have been started yet.")
        
        def show_daz_studio_log():
            """Show DAZ Studio log with default program"""
            # DAZ Studio logs are typically in user's Documents
            possible_paths = [
                os.path.join(os.path.expanduser("~"), "Documents", "DAZ 3D", "Studio", "log.txt"),
                os.path.join(os.path.expanduser("~"), "Documents", "DAZ 3D", "Studio4", "log.txt"),
                os.path.join(os.environ.get("APPDATA", ""), "DAZ 3D", "Studio4", "log.txt")
            ]
            
            log_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    log_path = path
                    break
            
            if log_path:
                try:
                    os.startfile(log_path)  # Open with default program on Windows
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to open log file: {e}")
            else:
                messagebox.showinfo("Log Not Found", "DAZ Studio log file not found. DAZ Studio may not have been run yet.")
        
        def show_about_overlord():
            """Show About dialog with logos, links, and patch notes"""
            about_window = tk.Toplevel(root)
            about_window.title("About Overlord")
            about_window.geometry("650x900")
            about_window.resizable(True, True)
            about_window.iconbitmap(resource_path(os.path.join("images", "favicon.ico")))
            theme_manager.register_widget(about_window, "root")
            
            # Center the window
            about_window.transient(root)
            about_window.grab_set()
            
            # Main frame (no scrolling needed now)
            main_frame = tk.Frame(about_window)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            theme_manager.register_widget(main_frame, "frame")
            
            # Overlord logo
            try:
                overlord_logo = tk.PhotoImage(file=resource_path(os.path.join("images", "overlordLogo.png")))
                overlord_logo_label = tk.Label(main_frame, image=overlord_logo, cursor="hand2")
                overlord_logo_label.image = overlord_logo  # Keep reference
                overlord_logo_label.pack(pady=(0, 10))
                theme_manager.register_widget(overlord_logo_label, "label")
                
                def open_overlord_github(event):
                    webbrowser.open("https://github.com/Laserwolve-Games/Overlord")
                
                overlord_logo_label.bind("<Button-1>", open_overlord_github)
            except Exception as e:
                logging.warning(f"Could not load Overlord logo: {e}")
            
            # GitHub repository link (text)
            github_repo_link = tk.Label(main_frame, text="https://github.com/Laserwolve-Games/Overlord", 
                                       font=("Arial", 10), cursor="hand2")
            github_repo_link.pack(pady=(0, 15))
            theme_manager.register_widget(github_repo_link, "label")
            
            # Version only
            version_label = tk.Label(main_frame, text=f"Version {get_display_version()}", 
                                   font=("Arial", 14, "bold"))
            version_label.pack(pady=(0, 20))
            theme_manager.register_widget(version_label, "label")
            
            # Patch Notes section
            patch_notes_label = tk.Label(main_frame, text="Latest Release Notes:", 
                                        font=("Arial", 12, "bold"))
            patch_notes_label.pack(pady=(10, 5), anchor="w")
            theme_manager.register_widget(patch_notes_label, "label")
            
            # Create text widget for patch notes with scrollbar
            patch_notes_frame = tk.Frame(main_frame)
            patch_notes_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
            theme_manager.register_widget(patch_notes_frame, "frame")
            
            patch_notes_text = tk.Text(patch_notes_frame, height=20, wrap=tk.WORD, 
                                     font=("Arial", 9), state=tk.DISABLED)
            patch_scrollbar = tk.Scrollbar(patch_notes_frame, orient=tk.VERTICAL, command=patch_notes_text.yview)
            patch_notes_text.configure(yscrollcommand=patch_scrollbar.set)
            
            theme_manager.register_widget(patch_notes_text, "text")
            theme_manager.register_widget(patch_scrollbar, "scrollbar")
            
            patch_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            patch_notes_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Function to render basic markdown formatting
            def render_markdown_to_text(markdown_text, text_widget):
                """Apply basic markdown formatting to text widget"""
                text_widget.config(state=tk.NORMAL)
                text_widget.delete(1.0, tk.END)
                
                # Configure text tags for formatting
                text_widget.tag_configure("heading1", font=("Arial", 14, "bold"))
                text_widget.tag_configure("heading2", font=("Arial", 12, "bold"))
                text_widget.tag_configure("heading3", font=("Arial", 11, "bold"))
                text_widget.tag_configure("bold", font=("Arial", 9, "bold"))
                text_widget.tag_configure("italic", font=("Arial", 9, "italic"))
                text_widget.tag_configure("code", font=("Courier", 9), background="#f0f0f0")
                text_widget.tag_configure("bullet", lmargin1=20, lmargin2=40)
                
                lines = markdown_text.split('\n')
                for line in lines:
                    line = line.rstrip()
                    
                    # Headers
                    if line.startswith('# '):
                        text_widget.insert(tk.END, line[2:] + '\n', "heading1")
                    elif line.startswith('## '):
                        text_widget.insert(tk.END, line[3:] + '\n', "heading2")
                    elif line.startswith('### '):
                        text_widget.insert(tk.END, line[4:] + '\n', "heading3")
                    # Bullet points
                    elif line.startswith('- ') or line.startswith('* '):
                        text_widget.insert(tk.END, f"• {line[2:]}\n", "bullet")
                    # Code blocks (simple detection)
                    elif line.startswith('```') or line.startswith('    '):
                        if line.startswith('```'):
                            text_widget.insert(tk.END, line[3:] + '\n', "code")
                        else:
                            text_widget.insert(tk.END, line + '\n', "code")
                    else:
                        # Handle inline formatting
                        current_pos = 0
                        while current_pos < len(line):
                            # Find next formatting marker
                            bold_pos = line.find('**', current_pos)
                            italic_pos = line.find('*', current_pos)
                            code_pos = line.find('`', current_pos)
                            
                            # Find the earliest formatting marker
                            next_marker = len(line)
                            marker_type = None
                            
                            if bold_pos != -1 and bold_pos < next_marker:
                                next_marker = bold_pos
                                marker_type = 'bold'
                            if italic_pos != -1 and italic_pos < next_marker and italic_pos != bold_pos:
                                next_marker = italic_pos
                                marker_type = 'italic'
                            if code_pos != -1 and code_pos < next_marker:
                                next_marker = code_pos
                                marker_type = 'code'
                            
                            # Insert normal text up to marker
                            if next_marker > current_pos:
                                text_widget.insert(tk.END, line[current_pos:next_marker])
                            
                            if marker_type == 'bold' and next_marker < len(line):
                                end_pos = line.find('**', next_marker + 2)
                                if end_pos != -1:
                                    text_widget.insert(tk.END, line[next_marker + 2:end_pos], "bold")
                                    current_pos = end_pos + 2
                                else:
                                    text_widget.insert(tk.END, line[next_marker:])
                                    break
                            elif marker_type == 'italic' and next_marker < len(line):
                                end_pos = line.find('*', next_marker + 1)
                                if end_pos != -1:
                                    text_widget.insert(tk.END, line[next_marker + 1:end_pos], "italic")
                                    current_pos = end_pos + 1
                                else:
                                    text_widget.insert(tk.END, line[next_marker:])
                                    break
                            elif marker_type == 'code' and next_marker < len(line):
                                end_pos = line.find('`', next_marker + 1)
                                if end_pos != -1:
                                    text_widget.insert(tk.END, line[next_marker + 1:end_pos], "code")
                                    current_pos = end_pos + 1
                                else:
                                    text_widget.insert(tk.END, line[next_marker:])
                                    break
                            else:
                                if next_marker < len(line):
                                    text_widget.insert(tk.END, line[next_marker:])
                                break
                        
                        text_widget.insert(tk.END, '\n')
                
                text_widget.config(state=tk.DISABLED)
            
            # Function to fetch and display patch notes
            def fetch_patch_notes():
                try:
                    # Fetch latest release info from GitHub API
                    api_url = "https://api.github.com/repos/Laserwolve-Games/Overlord/releases/latest"
                    
                    with urllib.request.urlopen(api_url, timeout=10) as response:
                        release_data = json.loads(response.read().decode())
                    
                    # Extract release information
                    tag_name = release_data.get('tag_name', 'Unknown')
                    release_name = release_data.get('name', 'Unknown Release')
                    body = release_data.get('body', 'No release notes available.')
                    published_at = release_data.get('published_at', '')
                    
                    # Format the date
                    if published_at:
                        try:
                            from datetime import datetime
                            date_obj = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                            formatted_date = date_obj.strftime('%B %d, %Y')
                        except:
                            formatted_date = published_at
                    else:
                        formatted_date = 'Unknown date'
                    
                    # Format the patch notes with markdown
                    patch_notes_content = f"# {release_name} ({tag_name})\n**Released:** {formatted_date}\n\n{body}"
                    
                    # Render with basic markdown formatting
                    render_markdown_to_text(patch_notes_content, patch_notes_text)
                    
                except Exception as e:
                    logging.warning(f"Could not fetch patch notes: {e}")
                    error_content = f"Could not load patch notes.\n\n**Error:** {str(e)}\n\nPlease visit: https://github.com/Laserwolve-Games/Overlord/releases/latest"
                    render_markdown_to_text(error_content, patch_notes_text)
            
            # Fetch patch notes in a separate thread to avoid blocking UI
            threading.Thread(target=fetch_patch_notes, daemon=True).start()
            
            # Initially show loading message
            patch_notes_text.config(state=tk.NORMAL)
            patch_notes_text.insert(1.0, "Loading latest release notes...")
            patch_notes_text.config(state=tk.DISABLED)
            
            # Laserwolve Games logo
            try:
                lwg_logo = tk.PhotoImage(file=resource_path(os.path.join("images", "laserwolveGamesLogo.png")))
                lwg_logo_label = tk.Label(main_frame, image=lwg_logo, cursor="hand2")
                lwg_logo_label.image = lwg_logo  # Keep reference
                lwg_logo_label.pack(pady=(10, 10))
                theme_manager.register_widget(lwg_logo_label, "label")
                
                def open_lwg_website(event):
                    webbrowser.open("https://laserwolvegames.com")
                
                lwg_logo_label.bind("<Button-1>", open_lwg_website)
            except Exception as e:
                logging.warning(f"Could not load Laserwolve Games logo: {e}")
            
            # Laserwolve Games website link
            lwg_link = tk.Label(main_frame, text="https://laserwolvegames.com", 
                              font=("Arial", 10), cursor="hand2")
            lwg_link.pack(pady=(5, 5))
            theme_manager.register_widget(lwg_link, "label")
            
            # Laserwolve Games GitHub organization link
            lwg_github_link = tk.Label(main_frame, text="https://github.com/Laserwolve-Games", 
                                     font=("Arial", 10), cursor="hand2")
            lwg_github_link.pack(pady=(0, 15))
            theme_manager.register_widget(lwg_github_link, "label")
            
            # Apply hyperlink styling based on theme
            def apply_link_style():
                if theme_manager.current_theme == "dark":
                    github_repo_link.config(fg="#5DADE2")  # Light blue for dark theme
                    lwg_link.config(fg="#5DADE2")
                    lwg_github_link.config(fg="#5DADE2")
                else:
                    github_repo_link.config(fg="#0066CC")  # Dark blue for light theme
                    lwg_link.config(fg="#0066CC")
                    lwg_github_link.config(fg="#0066CC")
            
            apply_link_style()
            
            def open_github_repo(event):
                webbrowser.open("https://github.com/Laserwolve-Games/Overlord")
            
            def open_lwg_link(event):
                webbrowser.open("https://laserwolvegames.com")
            
            def open_lwg_github(event):
                webbrowser.open("https://github.com/Laserwolve-Games")
            
            github_repo_link.bind("<Button-1>", open_github_repo)
            lwg_link.bind("<Button-1>", open_lwg_link)
            lwg_github_link.bind("<Button-1>", open_lwg_github)
            
            # Close button
            close_button = tk.Button(main_frame, text="Close", command=about_window.destroy,
                                   font=("Arial", 10), width=10)
            close_button.pack(pady=(10, 0))
            theme_manager.register_widget(close_button, "button")
        
        help_menu.add_command(label="Show Overlord Log", command=show_overlord_log)
        help_menu.add_command(label="Show Iray Server Log", command=show_iray_server_log)
        help_menu.add_command(label="Show DAZ Studio Log", command=show_daz_studio_log)
        help_menu.add_separator()
        help_menu.add_command(label="About Overlord", command=show_about_overlord)
        
        menubar.add_cascade(label="Help", menu=help_menu)
        
        root.config(menu=menubar)
        return menubar
    
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
        "Subject",
        "Animations",
        "Prop Animations",
        "Gear",
        "Gear Animations",
        "Output Directory"
    ]
    # Short/simple parameters
    param_params = [
        "Number of Instances",
        "Frame Rate"
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
                # Check if it's an Entry widget or Text widget
                if hasattr(text_widget, 'delete') and hasattr(text_widget, 'insert'):
                    try:
                        # Try Text widget methods first
                        text_widget.delete("1.0", tk.END)
                        text_widget.insert(tk.END, "\n".join(filenames))
                    except tk.TclError:
                        # If that fails, it's an Entry widget
                        text_widget.delete(0, tk.END)
                        text_widget.insert(0, "\n".join(filenames))
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

        if param == "Subject":
            value_entry = tk.Entry(file_table_frame, width=80, font=("Consolas", 10))
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            theme_manager.register_widget(value_entry, "entry")

            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=make_browse_file(
                    value_entry,
                    initialdir=os.path.join(os.path.expanduser("~"), "Documents"),
                    title="Select Subject File",
                    filetypes=(("DSON User File", "*.duf"),)
                ),
                width=8
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            theme_manager.register_widget(browse_button, "button")
            value_entries[param] = value_entry
            
            # Bind auto-save for subject
            value_entry.bind("<KeyRelease>", lambda e: auto_save_settings())
            value_entry.bind("<FocusOut>", lambda e: auto_save_settings())
        elif param == "Animations":
            text_widget = tk.Text(file_table_frame, width=80, height=5, font=("Consolas", 10))
            text_widget.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            theme_manager.register_widget(text_widget, "text")

            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=make_browse_files(
                    text_widget,
                    initialdir=os.path.join(os.path.expanduser("~"), "Documents"),
                    title="Select Animations",
                    filetypes=(("DSON User File", "*.duf"),)
                ),
                width=8
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            theme_manager.register_widget(browse_button, "button")
            value_entries[param] = text_widget
            
            # Bind auto-save for animations
            text_widget.bind("<KeyRelease>", lambda e: auto_save_settings())
            text_widget.bind("<FocusOut>", lambda e: auto_save_settings())
        elif param == "Prop Animations":
            text_widget = tk.Text(file_table_frame, width=80, height=5, font=("Consolas", 10))
            text_widget.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            theme_manager.register_widget(text_widget, "text")

            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=make_browse_files(
                    text_widget,
                    initialdir=os.path.join(os.path.expanduser("~"), "Documents"),
                    title="Select Prop Animation Files",
                    filetypes=(("DSON User File", "*.duf"),)
                ),
                width=8
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            theme_manager.register_widget(browse_button, "button")
            value_entries[param] = text_widget
            
            # Bind auto-save for prop animations
            text_widget.bind("<KeyRelease>", lambda e: auto_save_settings())
            text_widget.bind("<FocusOut>", lambda e: auto_save_settings())
        elif param == "Gear":
            text_widget = tk.Text(file_table_frame, width=80, height=5, font=("Consolas", 10))
            text_widget.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            theme_manager.register_widget(text_widget, "text")

            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=make_browse_files(
                    text_widget,
                    initialdir=os.path.join(os.path.expanduser("~"), "Documents"),
                    title="Select Gear Files",
                    filetypes=(("DSON User File", "*.duf"),)
                ),
                width=8
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            theme_manager.register_widget(browse_button, "button")
            value_entries[param] = text_widget
            
            # Bind auto-save for gear
            text_widget.bind("<KeyRelease>", lambda e: auto_save_settings())
            text_widget.bind("<FocusOut>", lambda e: auto_save_settings())
        elif param == "Gear Animations":
            text_widget = tk.Text(file_table_frame, width=80, height=5, font=("Consolas", 10))
            text_widget.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            theme_manager.register_widget(text_widget, "text")

            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=make_browse_files(
                    text_widget,
                    initialdir=os.path.join(os.path.expanduser("~"), "Documents"),
                    title="Select Gear Animation Files",
                    filetypes=(("DSON User File", "*.duf"),)
                ),
                width=8
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            theme_manager.register_widget(browse_button, "button")
            value_entries[param] = text_widget
            
            # Bind auto-save for gear animations
            text_widget.bind("<KeyRelease>", lambda e: auto_save_settings())
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




    # Short/simple parameters table - arranged horizontally
    current_column = 0
    for i, param in enumerate(param_params):
        param_label = tk.Label(param_table_frame, text=param, font=("Arial", 10), anchor="w")
        param_label.grid(row=1, column=current_column, padx=(10, 5), pady=5, sticky="w")
        theme_manager.register_widget(param_label, "label")

        value_entry = tk.Entry(param_table_frame, width=5, font=("Consolas", 10))
        if param == "Number of Instances":
            value_entry.insert(0, "1")
        elif param == "Frame Rate":
            value_entry.insert(0, "30")
        value_entry.grid(row=1, column=current_column+1, padx=(0, 20), pady=5, sticky="w")
        theme_manager.register_widget(value_entry, "entry")
        value_entries[param] = value_entry
        current_column += 2  # Move to next label/entry pair position

    # --- Render Shadows checkbox - positioned horizontally after other parameters ---
    render_shadows_var = tk.BooleanVar(value=True)
    render_shadows_label = tk.Label(param_table_frame, text="Render shadows", font=("Arial", 10), anchor="w")
    render_shadows_label.grid(row=1, column=current_column, padx=(10, 5), pady=5, sticky="w")
    theme_manager.register_widget(render_shadows_label, "label")
    render_shadows_checkbox = tk.Checkbutton(
        param_table_frame,
        variable=render_shadows_var,
        width=2,
        anchor="w"
    )
    render_shadows_checkbox.grid(row=1, column=current_column+1, padx=(0, 10), pady=5, sticky="w")
    theme_manager.register_widget(render_shadows_checkbox, "checkbutton")

    # Register settings save callback for cleanup
    def save_current_settings():
        current_settings = settings_manager.get_current_settings(value_entries, render_shadows_var)
        settings_manager.save_settings(current_settings)
    cleanup_manager.register_settings_callback(save_current_settings)

    saved_settings = settings_manager.load_settings()
    # Apply the loaded settings to the UI (now that all widgets are created)
    settings_manager.apply_settings(saved_settings, value_entries, render_shadows_var)

    # Apply command line arguments if provided (overrides saved settings)
    def apply_command_line_args():
        """Apply command line arguments to UI fields"""
        if cmd_args:
            if cmd_args.subject:
                value_entries["Subject"].delete(0, tk.END)
                value_entries["Subject"].insert(0, cmd_args.subject)
                
            if cmd_args.animations:
                value_entries["Animations"].delete("1.0", tk.END)
                value_entries["Animations"].insert("1.0", "\n".join(cmd_args.animations))
                
            if cmd_args.prop_animations:
                value_entries["Prop Animations"].delete("1.0", tk.END)
                value_entries["Prop Animations"].insert("1.0", "\n".join(cmd_args.prop_animations))
                
            if cmd_args.gear:
                value_entries["Gear"].delete("1.0", tk.END)
                value_entries["Gear"].insert("1.0", "\n".join(cmd_args.gear))
                
            if cmd_args.gear_animations:
                value_entries["Gear Animations"].delete("1.0", tk.END)
                value_entries["Gear Animations"].insert("1.0", "\n".join(cmd_args.gear_animations))
                
            if cmd_args.output_dir:
                value_entries["Output Directory"].delete(0, tk.END)
                value_entries["Output Directory"].insert(0, cmd_args.output_dir)
                
            if cmd_args.instances:
                value_entries["Number of Instances"].delete(0, tk.END)
                value_entries["Number of Instances"].insert(0, str(cmd_args.instances))
                
            if cmd_args.frame_rate:
                value_entries["Frame Rate"].delete(0, tk.END)
                value_entries["Frame Rate"].insert(0, str(cmd_args.frame_rate))
                
            if cmd_args.render_shadows is not None:
                render_shadows_var.set(cmd_args.render_shadows)
                
            logging.info("Command line arguments applied to UI fields")
    
    apply_command_line_args()

    # Log settings loading - settings loaded silently
    
    # Bind auto-save to key widgets
    value_entries["Output Directory"].bind("<FocusOut>", lambda e: auto_save_settings())
    value_entries["Number of Instances"].bind("<FocusOut>", lambda e: auto_save_settings())
    value_entries["Frame Rate"].bind("<FocusOut>", lambda e: auto_save_settings())
    
    # For checkboxes, bind to the variable change
    render_shadows_var.trace_add('write', auto_save_settings)

    # Helper function for processing display paths
    def process_display_path(path):
        """Process path for display: filter out admin paths, normalize slashes."""
        if not path:
            return ""
        
        # Don't display paths containing "admin" - return None to indicate no update should occur
        if "admin" in path.lower():
            return None
        
        # Replace backslashes with forward slashes
        return path.replace('\\', '/')
    
    def open_file_location(path):
        """Open the file location in Windows Explorer."""
        if not path:
            return
        
        try:
            # Convert back to backslashes for Windows explorer
            windows_path = path.replace('/', '\\')
            
            # If it's a zip path, extract the zip file path
            if '.zip\\' in windows_path.lower():
                zip_parts = windows_path.lower().split('.zip\\')
                zip_file_path = zip_parts[0] + '.zip'
                # Open the folder containing the zip file
                subprocess.run(['explorer', '/select,', zip_file_path], check=False)
            else:
                # For regular files, try to select the file
                if os.path.exists(windows_path):
                    subprocess.run(['explorer', '/select,', windows_path], check=False)
                else:
                    # If file doesn't exist, try to open the parent directory
                    parent_dir = os.path.dirname(windows_path)
                    if os.path.exists(parent_dir):
                        subprocess.run(['explorer', parent_dir], check=False)
        except Exception as e:
            logging.error(f"Error opening file location: {e}")

    # Create the menu bar (after all UI variables are defined)
    create_menu_bar()

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
    details_frame.place(relx=0.26, rely=0.75, anchor="nw", width=350, height=200)
    details_frame.pack_propagate(False)
    theme_manager.register_widget(details_frame, "frame")

    details_title = tk.Label(details_frame, text="Last Rendered Image Details", font=("Arial", 14, "bold"))
    details_title.pack(anchor="nw", pady=(0, 10))
    theme_manager.register_widget(details_title, "label")

    # Show only the path (no "Path: " prefix) - make it clickable like a hyperlink
    # Fixed height container to prevent shifting of elements below
    path_container = tk.Frame(details_frame, height=60)  # Fixed height for ~4 lines
    path_container.pack(anchor="nw", pady=(0, 5), fill="x")
    path_container.pack_propagate(False)  # Prevent resizing based on content
    theme_manager.register_widget(path_container, "frame")
    
    details_path = tk.Label(path_container, text="", font=("Consolas", 9), wraplength=330, justify="left", 
                          cursor="hand2", anchor="nw")
    details_path.pack(anchor="nw", fill="both", expand=True)
    theme_manager.register_widget(details_path, "label")
    
    # Apply hyperlink styling based on theme
    def apply_hyperlink_style():
        if theme_manager.current_theme == "light":
            details_path.config(fg="blue")
        else:
            details_path.config(fg="#5DADE2")  # Light blue for dark theme
    
    apply_hyperlink_style()
    
    # Register the hyperlink style function to be called when theme changes
    theme_manager.add_theme_change_callback(apply_hyperlink_style)
    
    # Store the current path for the click handler
    details_path.current_path = ""
    
    def on_path_click(event):
        """Handle click on path label."""
        if details_path.current_path:
            open_file_location(details_path.current_path)
    
    details_path.bind("<Button-1>", on_path_click)
    
    # Function to update the path display
    def update_details_path(path):
        """Update the details path with processing and store the original path."""
        processed_path = process_display_path(path)
        # Only update if the processed path is not None (None means don't update)
        if processed_path is not None:
            details_path.config(text=processed_path)
            details_path.current_path = processed_path  # Store for click handler

    # Add a button to copy the path to clipboard
    def copy_path_to_clipboard():
        path = details_path.current_path
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
    output_details_frame.place(relx=0.01, rely=0.75, anchor="nw", width=350, height=200)
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
    images_remaining_label.place(relx=0.01, rely=0.70, anchor="nw", width=250, height=18)
    theme_manager.register_widget(images_remaining_label, "label")
    estimated_time_remaining_label.place(relx=0.11, rely=0.70, anchor="nw", width=250, height=18)
    theme_manager.register_widget(estimated_time_remaining_label, "label")
    estimated_completion_at_label.place(relx=0.245, rely=0.70, anchor="nw", width=400, height=18)
    theme_manager.register_widget(estimated_completion_at_label, "label")

    progress_bar = ttk.Progressbar(root, variable=progress_var, maximum=100)
    # Place the progress bar just above the output_details_frame, matching its width and alignment
    progress_bar.place(relx=0.01, rely=0.72, anchor="nw", width=850, height=18)
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

    output_folder_count = tk.Label(output_details_frame, text="Sub-folders: ", font=("Arial", 10))
    output_folder_count.pack(anchor="nw", pady=(0, 5))
    theme_manager.register_widget(output_folder_count, "label")

    # Add Total Images to Render label (updated only on Start Render)
    output_total_images = tk.Label(output_details_frame, text="Total Images to Render: ", font=("Arial", 10))
    theme_manager.register_widget(output_total_images, "label")
    # output_total_images.pack(anchor="nw", pady=(0, 5))

    def update_output_details():
        """Update the output details with current folder statistics"""
        logging.debug("update_output_details: Starting update...")
        
        output_dir = value_entries["Output Directory"].get()
        logging.debug(f"update_output_details: Output directory: {output_dir}")
        
        if not os.path.exists(output_dir):
            output_folder_size.config(text="Folder Size: N/A")
            output_png_count.config(text="PNG Files: N/A")
            output_folder_count.config(text="Sub-folders: N/A")
            progress_var.set(0)
            images_remaining_var.set("Images remaining: --")
            logging.debug("update_output_details: Output directory doesn't exist")
            return
        try:
            total_size = 0
            png_count = 0
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
                    except (OSError, IOError):
                        continue
            
            size_str = format_file_size(total_size)
            output_folder_size.config(text=f"Folder Size: {size_str}")
            output_png_count.config(text=f"PNG Files: {png_count}")
            output_folder_count.config(text=f"Sub-folders: {folder_count}")
            logging.debug(f"update_output_details: Found {png_count} PNG files")
            
            # Update progress bar and images remaining label using successful moves count
            try:
                total_images_str = output_total_images.cget("text").replace("Total Images to Render: ", "").strip()
                logging.debug(f"update_output_details: Total images string: '{total_images_str}'")
                
                if not total_images_str:
                    progress_var.set(0)
                    images_remaining_var.set("Images remaining: --")
                    estimated_time_remaining_var.set("Estimated time remaining: --")
                    estimated_completion_at_var.set("Estimated completion at: --")
                    logging.debug("update_output_details: Total images string is empty")
                    return
                total_images = int(total_images_str) if total_images_str.isdigit() else None
                logging.debug(f"update_output_details: Parsed total images: {total_images}")
                
                # Since we removed EXR conversion and ZIP functionality,
                # progress tracking is simplified to just count PNG files in output directory
                # Get the directory stats without ZIP counting
                total_size, png_count, folder_count = get_directory_stats(output_dir)
                
                if total_images and total_images > 0:
                    # Use PNG count as a simple approximation of progress
                    completed_images = png_count
                    percent = min(100, (completed_images / total_images) * 100)
                    progress_var.set(percent)
                    remaining = max(0, total_images - completed_images)
                    images_remaining_var.set(f"Images remaining: {remaining}")
                    logging.info(f"update_output_details: Updated progress - {completed_images}/{total_images} images ({percent:.1f}%), {remaining} remaining")
                    update_estimated_time_remaining(remaining)
                else:
                    progress_var.set(0)
                    images_remaining_var.set("Images remaining: --")
                    estimated_time_remaining_var.set("Estimated time remaining: --")
                    estimated_completion_at_var.set("Estimated completion at: --")
                    logging.debug("update_output_details: Total images is 0 or None")
            except Exception as e:
                progress_var.set(0)
                images_remaining_var.set("Images remaining: --")
                estimated_time_remaining_var.set("Estimated time remaining: --")
                estimated_completion_at_var.set("Estimated completion at: --")
                logging.error(f"update_output_details: Error updating progress: {e}")
        except Exception as e:
            output_folder_size.config(text="Folder Size: Error")
            output_png_count.config(text="PNG Files: Error")
            output_folder_count.config(text="Sub-folders: Error")
            progress_var.set(0)
            images_remaining_var.set("Images remaining: --")
            logging.error(f"update_output_details: Error in folder stats: {e}")

    no_img_label = tk.Label(right_frame, font=("Arial", 12))
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
                # Always display the mapped output path instead of server path
                display_path = map_server_path_to_output_path(newest_img_path)
                update_details_path(display_path)  # Process and display path
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
            update_details_path("")  # Clear the path
            details_dim.config(text="Dimensions: ")
            details_size.config(text="Size: ")
            no_img_label.lift()
            if not getattr(show_last_rendered_image, 'last_no_img_logged', False):
                show_last_rendered_image.last_no_img_logged = True
        
        # Force garbage collection to clean up any remaining references
        gc.collect()

    def map_server_path_to_output_path(server_path):
        """Since we removed the intermediate server directory, just return the path as-is."""
        return server_path.replace('/', '\\') if server_path else server_path

    def display_specific_image(image_path):
        """Display a specific image in the UI."""
        if not os.path.exists(image_path):
            return
        
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
            with Image.open(image_path) as verify_img:
                verify_img.verify()  # Will raise if the image is incomplete or corrupt
            
            # If verification passes, reopen for display
            with Image.open(image_path) as img:
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
            
            with Image.open(image_path) as orig_img:
                width, height = orig_img.size
            
            file_size = os.path.getsize(image_path)
            # Always display the mapped output path instead of server path
            display_path = map_server_path_to_output_path(image_path)
            update_details_path(display_path)  # Process and display path
            details_dim.config(text=f"Dimensions: {width} x {height}")
            details_size.config(text=f"Size: {file_size/1024:.1f} KB")
            
            tk_img = ImageTk.PhotoImage(img_copy)
            cleanup_manager.register_image_reference(tk_img)  # Register for cleanup
            img_label.config(image=tk_img)
            img_label.image = tk_img
            no_img_label.lower()
            
            # Only log if the image path has changed
            if getattr(display_specific_image, 'last_logged_img_path', None) != image_path:
                logging.info(f'Displaying image: {image_path}')
                display_specific_image.last_logged_img_path = image_path
            
        except Exception as e:
            logging.error(f'Error displaying specific image {image_path}: {e}')
        
        # Force garbage collection to clean up any remaining references
        gc.collect()

    def watchdog_image_update(new_image_path):
        """Simplified callback for when new images are available (no EXR processing)."""
        def update_ui():
            try:
                output_dir = value_entries["Output Directory"].get()
                
                # Update if the new image is in the output directory and exists
                if (new_image_path.startswith(output_dir) and os.path.exists(new_image_path)):
                    show_last_rendered_image()
                    logging.debug(f'UI updated for new image: {new_image_path}')
                else:
                    # Fallback: just refresh the last rendered image
                    show_last_rendered_image()
            except Exception as e:
                logging.error(f'Error updating UI for new image {new_image_path}: {e}')
        
        # Schedule the update on the main thread
        try:
            root.after(100, update_ui)  # Small delay to ensure file is fully written
        except Exception as e:
            logging.error(f'Error scheduling UI update for new image: {e}')

    # Update image when output directory changes or after render
    def on_output_dir_change(*args):
        new_output_dir = value_entries["Output Directory"].get()
        logging.info(f'Output Directory changed to: {new_output_dir}')
        
        # Since we removed EXR processing, just refresh the image display
        root.after(200, show_last_rendered_image)
        root.after(200, update_output_details)
    value_entries["Output Directory"].bind("<FocusOut>", lambda e: on_output_dir_change())
    value_entries["Output Directory"].bind("<Return>", lambda e: on_output_dir_change())

    def start_render():
        # Prevent multiple render starts
        if button.cget("state") == "disabled":
            logging.info("Start Render already in progress, ignoring additional click")
            return

        # Validate Subject, Animations and Output Directory before launching render
        subject_file = value_entries["Subject"].get().strip()
        animations = value_entries["Animations"].get("1.0", tk.END).strip().replace("\\", "/").split("\n")
        animations = [file for file in animations if file]
        output_dir = value_entries["Output Directory"].get().strip()
        if not subject_file:
            from tkinter import messagebox
            messagebox.showerror("Missing Subject File", "Please specify a Subject file before starting the render.")
            logging.info("Start Render cancelled: No Subject file specified.")
            return
        if not animations:
            from tkinter import messagebox
            messagebox.showerror("Missing Animation Files", "Please specify at least one Animation file before starting the render.")
            logging.info("Start Render cancelled: No Animation files specified.")
            return
        if not output_dir:
            from tkinter import messagebox
            messagebox.showerror("Missing Output Directory", "Please specify an Output Directory before starting the render.")
            logging.info("Start Render cancelled: No Output Directory specified.")
            return
        
        # Validate all files exist and have .duf extension
        files_to_check = []
        
        # Add Subject file
        if subject_file:
            files_to_check.append(("Subject", subject_file))
        
        # Add Animation files
        for animation_file in animations:
            files_to_check.append(("Animation", animation_file))
        
        # Add Prop Animation files
        prop_animations_text = value_entries["Prop Animations"].get("1.0", tk.END).strip()
        if prop_animations_text:
            prop_animations = [f.strip() for f in prop_animations_text.split('\n') if f.strip()]
            for prop_animation_file in prop_animations:
                files_to_check.append(("Prop Animation", prop_animation_file))
        
        # Add Gear files
        gear_text = value_entries["Gear"].get("1.0", tk.END).strip()
        if gear_text:
            gear_files = [f.strip() for f in gear_text.split('\n') if f.strip()]
            for gear_file in gear_files:
                files_to_check.append(("Gear", gear_file))
        
        # Add Gear Animation files
        gear_animations_text = value_entries["Gear Animations"].get("1.0", tk.END).strip()
        if gear_animations_text:
            gear_animations = [f.strip() for f in gear_animations_text.split('\n') if f.strip()]
            for gear_animation_file in gear_animations:
                files_to_check.append(("Gear Animation", gear_animation_file))
        
        # Check each file
        missing_files = []
        invalid_extensions = []
        
        for file_type, file_path in files_to_check:
            # Check if file exists
            if not os.path.isfile(file_path):
                missing_files.append(f"{file_type}: {file_path}")
            # Check if file has .duf extension
            elif not file_path.lower().endswith('.duf'):
                invalid_extensions.append(f"{file_type}: {file_path}")
        
        # Display errors if any files are missing or invalid
        if missing_files or invalid_extensions:
            from tkinter import messagebox
            error_parts = []
            if missing_files:
                error_parts.append("The following files do not exist:")
                error_parts.extend([f"  • {file}" for file in missing_files])
            
            if invalid_extensions:
                if error_parts:
                    error_parts.append("")  # Add blank line
                error_parts.append("The following files are not .duf files:")
                error_parts.extend([f"  • {file}" for file in invalid_extensions])
            
            error_message = "\n".join(error_parts)
            messagebox.showerror("File Validation Error", error_message)
            logging.info(f"Start Render cancelled: File validation failed - {error_message}")
            return
        
        # Disable Start Render button and enable Stop Render button
        button.config(state="disabled")
        stop_button.config(state="normal")
        root.update_idletasks()  # Force UI update
        
        # Start the render process in a background thread to keep UI responsive
        def start_render_background():
            try:
                # First, ensure all render-related processes are stopped
                logging.info('Start Render button clicked')
                logging.info('Closing any existing Iray Server and DAZ Studio instances...')
                
                # Stop file monitoring first to prevent conflicts
                cleanup_manager.stop_file_monitoring()
                
                # Kill all existing render-related processes
                kill_render_related_processes()
                
                # Clean up database and cache from any previous sessions
                cleanup_iray_database_and_cache()
                
                logging.info('All previous instances closed. Starting fresh Iray Server...')
                
                # Since we removed the intermediate server directory, just clean up the main script directory
                script_dir = os.path.dirname(os.path.abspath(__file__))
                logging.info(f"Cleanup in script directory: {script_dir}")
                cleanup_iray_files_in_directory(script_dir, with_retries=False)
                
                if not start_iray_server():  # Start Iray Server
                    logging.error('Failed to start Iray Server')
                    return  # Exit early if server startup failed
                
                logging.info('Iray Server started - skipping web UI configuration')
                
                # Define session completion callback for Iray Server restart
                def on_session_complete():
                    """Called when RENDERS_PER_SESSION images have been successfully processed"""
                    logging.info(f'Session complete: {RENDERS_PER_SESSION} images processed - starting Iray Server restart')
                    
                    def restart_iray_background():
                        try:
                            # Stop Iray Server processes only (keep DAZ Studio running)
                            cleanup_manager.stop_iray_server()
                            
                            # Clean up database and cache
                            cleanup_iray_database_and_cache()
                            
                            logging.info('Cleanup complete, restarting Iray Server only...')
                            
                            # Restart Iray Server
                            if not start_iray_server():
                                logging.error('Failed to restart Iray Server')
                                return
                            
                            logging.info('Iray Server restarted successfully')
                            
                            # Since we removed server output directory, no need to clean/recreate it
                            
                            # Since DAZ Studio continues running, just refresh the UI
                            logging.info('Session restart complete for existing DAZ Studio instances')
                            image_output_dir = value_entries["Output Directory"].get().replace("\\", "/")
                            
                            logging.info('Session restart complete - ready for next cycle')
                        except Exception as e:
                            logging.error(f'Error during session restart: {e}')
                    
                    # Run restart in background thread to avoid blocking file operations
                    restart_thread = threading.Thread(target=restart_iray_background, daemon=True)
                    restart_thread.start()
                
                # Start background thread to wait for render completion
                def wait_for_completion():
                    try:
                        # Define callback to run on main thread when renders complete
                        def on_renders_complete():
                            logging.info('Starting render completion cleanup...')
                            
                            # Move heavy operations to background thread to avoid freezing UI
                            def cleanup_and_restart_background():
                                try:
                                    # Stop Iray Server processes only (keep DAZ Studio running)
                                    cleanup_manager.stop_iray_server()
                                    
                                    # Clean up database and cache
                                    cleanup_iray_database_and_cache()
                                    
                                    logging.info('Cleanup complete, restarting Iray Server only...')
                                    
                                    # Restart Iray Server
                                    if not start_iray_server():
                                        logging.error('Failed to restart Iray Server')
                                        raise Exception("Iray Server restart failed")
                                    logging.info('Iray Server restarted')
                                    # Since we removed server output directory, no cleanup needed
                                    
                                    logging.info('Iray Server restarted - skipping web UI reconfiguration')
                                    
                                    # Since DAZ Studio no longer needs to restart when Iray Server restarts,
                                    # just refresh the UI for the existing DAZ instances
                                    logging.info('UI refresh for existing DAZ Studio instances')
                                    image_output_dir = value_entries["Output Directory"].get().replace("\\", "/")
                                    
                                    logging.info('Render completion cycle finished successfully - Iray Server restarted, DAZ Studio instances continue running')
                                except Exception as cleanup_e:
                                    logging.error(f'Error during render completion cleanup/restart: {cleanup_e}')
                                    # Still re-enable buttons even if cleanup fails - schedule on main thread
                                    root.after(0, lambda: (button.config(state="normal"), stop_button.config(state="disabled")))
                            
                            # Start the heavy operations in a background thread
                            cleanup_thread = threading.Thread(target=cleanup_and_restart_background, daemon=True)
                            cleanup_thread.start()
                        
                        # No longer monitoring completion via web UI - just continue with file monitoring
                        logging.info('Render process started - monitoring via file system only')
                    except Exception as e:
                        logging.error(f'Error in render completion monitoring: {e}')
                
                # Continue with the rest of the render setup on UI thread
                root.after(0, lambda: continue_render_setup(on_session_complete))
                
            except Exception as e:
                logging.error(f"Failed to start render: {e}")
                # Re-enable Start Render button and disable Stop Render button on error
                root.after(0, lambda: (button.config(state="normal"), stop_button.config(state="disabled")))
        
        def continue_render_setup(session_completion_callback):
            try:
                logging.info("continue_render_setup: Starting render setup continuation...")
                # Continue with rest of render setup
                complete_render_setup(session_completion_callback)
                logging.info("continue_render_setup: Render setup completed successfully")
                
            except Exception as e:
                logging.error(f"Failed to continue render setup: {e}")
                import traceback
                logging.error(f"Full traceback: {traceback.format_exc()}")
                # Re-enable Start Render button and disable Stop Render button on error
                button.config(state="normal")
                stop_button.config(state="disabled")
        
        # Start the background process
        render_thread = threading.Thread(target=start_render_background, daemon=True)
        render_thread.start()
        
    def complete_render_setup(session_completion_callback=None):
        logging.info("complete_render_setup: Starting total images calculation...")
        
        # Get animations again (since we're in a different scope now)
        animations = value_entries["Animations"].get("1.0", tk.END).strip().replace("\\", "/").split("\n")
        animations = [file for file in animations if file]
        logging.info(f"complete_render_setup: Found {len(animations)} animation files")
        
        # Calculate and display total images to render (update label)
        def get_angles_from_subject(subject_path):
            """Read the angles property from the subject file's JSON."""
            try:
                with open(subject_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    json_start = content.find('{')
                    if json_start == -1:
                        return 16  # Default value
                    data = json.loads(content[json_start:])
                    angles = data.get('asset_info', {}).get('angles')
                    return angles if angles is not None else 16
            except Exception:
                return 16  # Default value if can't read or parse

        def get_frames_from_animation(animation_path):
            """Get the number of frames from an animation file."""
            try:
                with open(animation_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    json_start = content.find('{')
                    if json_start == -1:
                        return 1  # Static animation
                    data = json.loads(content[json_start:])
                    animations = data.get('scene', {}).get('animations', [])
                    for anim in animations:
                        keys = anim.get('keys', [])
                        if len(keys) > 1:
                            return len(keys)
                    return 1  # Static animation if no multi-frame animation found
            except Exception:
                return 1  # Default to static if can't read

        def calculate_total_images():
            """Calculate total images based on subject, animations, gear, and settings."""
            # Get subject file
            subject_path = value_entries["Subject"].get().strip()
            if not subject_path:
                return None
                
            # Get number of angles from subject file
            angles = get_angles_from_subject(subject_path)
            logging.info(f"complete_render_setup: Subject angles: {angles}")
            
            # Get animation files
            animations = value_entries["Animations"].get("1.0", tk.END).strip().replace("\\", "/").split("\n")
            animations = [file.strip() for file in animations if file.strip()]
            
            # Get gear files
            gear_files = value_entries["Gear"].get("1.0", tk.END).strip().replace("\\", "/").split("\n")
            gear_files = [file.strip() for file in gear_files if file.strip()]
            logging.info(f"complete_render_setup: Found {len(gear_files)} gear files")
            
            # If no animations, it's a static render (1 frame)
            if not animations:
                total_frames = 1
                animation_count = 1  # One static render
                logging.info("complete_render_setup: No animations found - using static render")
            else:
                total_frames = 0
                animation_count = 0
                for animation_path in animations:
                    logging.info(f"complete_render_setup: Processing animation: {animation_path}")
                    if animation_path.lower().endswith('.duf'):
                        frames = get_frames_from_animation(animation_path)
                        total_frames += frames
                        animation_count += 1
                        logging.info(f"complete_render_setup: Animation {animation_path} has {frames} frames")
                    else:
                        logging.info(f"complete_render_setup: Skipping {animation_path} - not a .duf file")
            
            logging.info(f"complete_render_setup: Final animation_count: {animation_count}, total_frames: {total_frames}")
            
            if animation_count == 0:
                logging.warning("complete_render_setup: No valid animations found, returning None")
                return None
                
            # Calculate renders per animation:
            # - Base render (without gear): angles * frames_per_animation
            # - Gear renders: angles * frames_per_animation * number_of_gear_files
            gear_count = len(gear_files) if gear_files else 0
            renders_per_animation = 1 + gear_count  # 1 base render + 1 per gear file
            
            # Total images = animation_count * renders_per_animation * angles * avg_frames_per_animation
            avg_frames_per_animation = total_frames / animation_count if animation_count > 0 else 1
            total_images = animation_count * renders_per_animation * angles * avg_frames_per_animation
            
            # If Render Shadows is checked, double the total images
            if render_shadows_var.get():
                total_images *= 2
                logging.info("complete_render_setup: Shadows enabled - doubling total images")
                
            logging.info(f"complete_render_setup: Calculation - {animation_count} animations × {renders_per_animation} renders/anim × {angles} angles × {avg_frames_per_animation:.1f} avg_frames = {total_images}")
            return int(total_images)

        total_images = None
        try:
            total_images = calculate_total_images()
            logging.info(f"complete_render_setup: Total images calculated: {total_images}")
        except Exception as e:
            logging.warning(f"Error calculating total images: {e}")
            total_images = None
            
        if total_images is not None:
            output_total_images.config(text=f"Total Images to Render: {total_images}")
            logging.info(f"complete_render_setup: Updated total images label to: {total_images}")
        else:
            output_total_images.config(text="Total Images to Render: ")
            logging.info("complete_render_setup: Set total images label to empty")
        
        # Immediately update the progress details after setting total images
        logging.info("complete_render_setup: Calling update_output_details()...")
        update_output_details()
        logging.info("complete_render_setup: update_output_details() completed")

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
        # Use "Animations" and treat as files
        animations_json = json.dumps(animations)
        
        # Get the new file lists
        prop_animations = value_entries["Prop Animations"].get("1.0", tk.END).strip().replace("\\", "/").split("\n")
        prop_animations = [file for file in prop_animations if file]
        prop_animations_json = json.dumps(prop_animations)
        
        gear = value_entries["Gear"].get("1.0", tk.END).strip().replace("\\", "/").split("\n")
        gear = [file for file in gear if file]
        gear_json = json.dumps(gear)
        
        gear_animations = value_entries["Gear Animations"].get("1.0", tk.END).strip().replace("\\", "/").split("\n")
        gear_animations = [file for file in gear_animations if file]
        gear_animations_json = json.dumps(gear_animations)
        
        subject_file = value_entries["Subject"].get()
        image_output_dir = value_entries["Output Directory"].get().replace("\\", "/")
        num_instances = value_entries["Number of Instances"].get()
        log_size = LOG_SIZE_MB * 1000000  # Convert MBs to bytes (hardcoded constant)
        frame_rate = value_entries["Frame Rate"].get()

        try:
            num_instances_int = int(num_instances)
        except Exception:
            num_instances_int = 1

        # Add render_shadows to json_map
        render_shadows = render_shadows_var.get()
        # Since we removed the intermediate server directory, use the final output directory
        results_directory_path = image_output_dir
        json_map = (
            f'{{'
            f'"num_instances": "{num_instances}", '
            f'"image_output_dir": "{image_output_dir}", '
            f'"frame_rate": "{frame_rate}", '
            f'"subject_file": "{subject_file}", '
            f'"animations": {animations_json}, '
            f'"prop_animations": {prop_animations_json}, '
            f'"gear": {gear_json}, '
            f'"gear_animations": {gear_animations_json}, '
            f'"template_path": "{template_path}", '
            f'"render_shadows": {str(render_shadows).lower()}, '
            f'"results_directory_path": "{results_directory_path}"'
            f'}}'
        )

        def create_daz_command():
            """Create the DAZ Studio command array with all required parameters."""
            return create_daz_command_array(daz_executable_path, json_map, log_size, render_script_path)

        def run_instance():
            logging.info('Launching Daz Studio render instance')
            command = create_daz_command()
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
                # Since we removed EXR file monitoring, just log completion
                logging.info('Render instances launched successfully, images will be saved directly to output directory')

        run_all_instances()

    def kill_render_related_processes():
        """Kill all Daz Studio and Iray Server processes. Also resets UI progress labels."""
        logging.info('Killing all render-related processes (DAZStudio, Iray Server)')
        # Stop file monitoring first
        cleanup_manager.stop_file_monitoring()
        killed_daz = 0
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
            main.dazstudio_killed_by_user = True
            logging.info(f'Killed {killed_daz} DAZStudio process(es). Iray Server stopped via cleanup manager.')
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
        
        # Immediately disable the stop button to prevent multiple clicks
        stop_button.config(state="disabled")
        root.update_idletasks()  # Force UI update
        
        try:
            # Signal any running IrayServerActions operations to stop
            if hasattr(cleanup_manager, 'iray_actions') and cleanup_manager.iray_actions:
                cleanup_manager.iray_actions.request_stop()
                logging.info('Signaled IrayServerActions to stop')
            
            # Stop file monitoring first to prevent race conditions
            logging.info('Stopping file monitoring and conversion...')
            cleanup_manager.stop_file_monitoring()
            
            # Then kill render processes
            logging.info('Stopping render processes...')
            kill_render_related_processes()
            
            # Clean up database and cache after processes are killed
            logging.info('Cleaning up Iray database and cache...')
            cleanup_iray_database_and_cache()
            
        except Exception as e:
            logging.error(f'Error during stop render: {e}')
        finally:
            # Always re-enable Start Render button, even if there were errors
            button.config(state="normal")
            logging.info('Stop render completed')

    # Initial display setup
    root.after(500, show_last_rendered_image)  # Initial image load

    # --- Buttons Section ---
    buttons_frame = tk.Frame(root)
    buttons_frame.place(relx=0.0, rely=0.9, anchor="nw")
    theme_manager.register_widget(buttons_frame, "frame")

    button = tk.Button(buttons_frame, text="Start Render", command=start_render, font=("Arial", 16, "bold"), width=16, height=2)
    button.pack(side="left", padx=(20, 10), pady=10)
    theme_manager.register_widget(button, "button")

    stop_button = tk.Button(
        buttons_frame,
        text="Stop Render",
        command=stop_render,
        font=("Arial", 16, "bold"),
        width=16,
        height=2,
        state="disabled"  # Initially disabled until Start Render is clicked
    )
    stop_button.pack(side="left", padx=10, pady=10)
    theme_manager.register_widget(stop_button, "button")

    # Auto-start render if requested
    def auto_start_render_if_requested():
        """Auto-start render if the --startRender flag was passed"""
        if auto_start_render:
            logging.info("Auto-starting render due to --startRender flag")
            
            # Quick validation check before auto-starting
            subject_file = value_entries["Subject"].get().strip()
            animations = value_entries["Animations"].get("1.0", tk.END).strip().replace("\\", "/").split("\n")
            animations = [file for file in animations if file]
            output_dir = value_entries["Output Directory"].get().strip()
            
            if not subject_file or not animations or not output_dir:
                logging.warning("Auto-start render cancelled: Missing required fields (Subject, Animations, or Output Directory)")
                logging.info("Please fill in all required fields before using --startRender")
                return
            
            # Use root.after to ensure UI is fully loaded before starting render
            root.after(1000, start_render)  # Wait 1 second for UI to be ready
    
    # Schedule auto-start check after UI is ready
    root.after(100, auto_start_render_if_requested)

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
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Overlord - DAZ Studio Render Management Tool')
    parser.add_argument('--startRender', action='store_true', 
                        help='Automatically start render when application launches')
    parser.add_argument('--headless', action='store_true',
                        help='Run in headless mode without UI (automatically starts render)')
    
    # Input file arguments
    parser.add_argument('--subject', type=str, 
                        help='Path to the subject .duf file')
    parser.add_argument('--animations', nargs='*', type=str, 
                        help='One or more animation .duf files')
    parser.add_argument('--prop-animations', nargs='*', type=str, 
                        help='One or more prop animation .duf files')
    parser.add_argument('--gear', nargs='*', type=str, 
                        help='One or more gear .duf files')
    parser.add_argument('--gear-animations', nargs='*', type=str, 
                        help='One or more gear animation .duf files')
    parser.add_argument('--output-dir', type=str, 
                        help='Output directory for rendered images')
    
    # Render settings arguments
    parser.add_argument('--instances', type=int, 
                        help='Number of render instances to run')
    parser.add_argument('--frame-rate', type=int, 
                        help='Frame rate for animations')
    parser.add_argument('--render-shadows', action='store_true', default=None,
                        help='Enable shadow rendering')
    parser.add_argument('--no-render-shadows', dest='render_shadows', action='store_false',
                        help='Disable shadow rendering')
    
    args = parser.parse_args()
    
    # Pass the auto-start flag, headless mode, and all arguments to main
    exit_code = main(auto_start_render=args.startRender, cmd_args=args, headless=args.headless)
    if exit_code is not None:
        sys.exit(exit_code)
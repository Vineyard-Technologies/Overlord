import tkinter as tk
from tkinter import filedialog
import os
import subprocess
import sys
import webbrowser
import json
from PIL import Image, ImageTk
import time
import logging
from version import __version__ as overlord_version

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def setup_logger():
    # Try to write log to %APPDATA%/Overlord/log.txt (user-writable)
    appdata = os.environ.get('APPDATA')
    if appdata:
        log_dir = os.path.join(appdata, 'Overlord')
    else:
        # Fallback to user's home directory
        log_dir = os.path.join(os.path.expanduser('~'), 'Overlord')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'log.txt')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[logging.FileHandler(log_path, encoding='utf-8'), logging.StreamHandler()]
    )
    logging.info(f'--- Overlord started --- (log file: {log_path})')

def main():
    setup_logger()
    logging.info('Application launched')
    # Create the main window
    root = tk.Tk()
    root.title(f"Overlord {overlord_version}")
    root.iconbitmap(resource_path(os.path.join("assets", "favicon.ico")))  # Set the application icon

    # Maximize the application window
    root.state("zoomed")

    # Load and display the logo image
    logo = tk.PhotoImage(file=resource_path(os.path.join("assets", "overlordLogo.png")))
    logo_label = tk.Label(root, image=logo, cursor="hand2")
    logo_label.image = logo  # Keep a reference to avoid garbage collection
    logo_label.place(anchor="nw", x=10, y=10)  # Place in upper left corner, 10px down and right

    # Add Laserwolve Games logo to upper right corner
    lwg_logo = tk.PhotoImage(file=resource_path(os.path.join("assets", "laserwolveGamesLogo.png")))
    lwg_logo_label = tk.Label(root, image=lwg_logo, cursor="hand2")
    lwg_logo_label.image = lwg_logo  # Keep a reference to avoid garbage collection
    # Place in upper right using place geometry manager
    lwg_logo_label.place(anchor="nw", x=700)
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
    param_table_frame = tk.Frame(root)
    param_table_frame.pack(pady=(20, 10), anchor="nw", side="top")  # 20px down from file_table_frame

    # File/folder path parameters
    file_params = [
        "Source Sets",
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

    # File/folder path parameters table
    for i, param in enumerate(file_params):
        param_label = tk.Label(file_table_frame, text=param, font=("Arial", 10), anchor="w")
        param_label.grid(row=i+1, column=0, padx=10, pady=5, sticky="w")

        if param == "Source Sets":
            text_widget = tk.Text(file_table_frame, width=80, height=5, font=("Consolas", 10))  # Changed height to 5
            text_widget.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            def browse_folders_append():
                # Start in user's Documents directory
                documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
                foldername = filedialog.askdirectory(
                    initialdir=documents_dir,
                    title="Select Source Set Folder"
                )
                # askdirectory only allows one folder at a time, so allow multiple by repeated selection
                if foldername:
                    current = text_widget.get("1.0", tk.END).strip()
                    current_folders = set(current.split("\n")) if current else set()
                    if foldername not in current_folders:
                        if current:
                            text_widget.insert(tk.END, "\n" + foldername)
                        else:
                            text_widget.insert(tk.END, foldername)
            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=browse_folders_append
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            # Add Clear button below Browse button
            def clear_source_sets():
                text_widget.delete("1.0", tk.END)
            clear_button = tk.Button(
                file_table_frame,
                text="Clear",
                command=clear_source_sets
            )
            clear_button.grid(row=i+1, column=2, padx=5, pady=(100, 5))
            value_entries[param] = text_widget
        elif param == "Output Directory":
            value_entry = tk.Entry(file_table_frame, width=80, font=("Consolas", 10))
            default_img_dir = os.path.join(
                os.path.expanduser("~"),
                "Downloads", "output"
            )
            value_entry.insert(0, default_img_dir)
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")

            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=make_browse_folder(
                    value_entry,
                    initialdir=default_img_dir,
                    title="Select Output Directory"
                )
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            value_entries[param] = value_entry



    # Short/simple parameters table
    for i, param in enumerate(param_params):
        param_label = tk.Label(param_table_frame, text=param, font=("Arial", 10), anchor="w")
        param_label.grid(row=i+1, column=0, padx=10, pady=5, sticky="w")

        value_entry = tk.Entry(param_table_frame, width=5, font=("Consolas", 10))
        if param == "Number of Instances":
            value_entry.insert(0, "1")
        elif param == "Log File Size (MBs)":
            value_entry.insert(0, "500")
        elif param == "Frame Rate":
            value_entry.insert(0, "30")
        value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
        value_entries[param] = value_entry

    # --- Last Rendered Image Section ---
    right_frame = tk.Frame(root)
    right_frame.place(relx=0.73, rely=0.0, anchor="n", width=1024, height=1024)

    right_frame.config(highlightbackground="black", highlightthickness=1)

    # Place img_label directly in right_frame
    img_label = tk.Label(right_frame)
    img_label.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)

    # --- Image Details Column ---
    # Place details_frame to the right of param_table_frame
    details_frame = tk.Frame(root, width=350)
    details_frame.place(relx=0.25, rely=0.6, anchor="nw", width=350, height=200)
    details_frame.pack_propagate(False)

    details_title = tk.Label(details_frame, text="Last Rendered Image Details", font=("Arial", 14, "bold"))
    details_title.pack(anchor="nw", pady=(0, 10))

    # Show only the path (no "Path: " prefix)
    details_path = tk.Label(details_frame, text="", font=("Consolas", 9), wraplength=330, justify="left")
    details_path.pack(anchor="nw", pady=(0, 5))

    # Add a button to copy the path to clipboard
    def copy_path_to_clipboard():
        path = details_path.cget("text")
        if path:
            root.clipboard_clear()
            root.clipboard_append(path)
            root.update()  # Keeps clipboard after window closes

    copy_btn = tk.Button(details_frame, text="Copy Path", command=copy_path_to_clipboard, font=("Arial", 9))
    copy_btn.pack(anchor="nw", pady=(0, 8))

    details_size = tk.Label(details_frame, text="Size: ", font=("Arial", 10))
    details_size.pack(anchor="nw", pady=(0, 5))
    details_dim = tk.Label(details_frame, text="Dimensions: ", font=("Arial", 10))
    details_dim.pack(anchor="nw", pady=(0, 5))

    no_img_label = tk.Label(right_frame, text="No images found in output directory", font=("Arial", 12))
    no_img_label.place(relx=0.5, rely=0.5, anchor="center")
    no_img_label.lower()  # Hide initially

    def find_newest_image(directory):
        image_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
        newest_file = None
        newest_time = None
        for rootdir, _, files in os.walk(directory):
            for fname in files:
                if fname.lower().endswith(image_exts):
                    fpath = os.path.join(rootdir, fname)
                    mtime = os.path.getmtime(fpath)
                    if newest_time is None or mtime > newest_time:
                        newest_time = mtime
                        newest_file = fpath
        return newest_file

    def show_last_rendered_image():
        output_dir = value_entries["Output Directory"].get()
        newest_img_path = find_newest_image(output_dir)
        if newest_img_path and os.path.exists(newest_img_path):
            try:
                img = Image.open(newest_img_path).convert("RGBA")  # Ensure image is in RGBA mode
                # Handle transparency by adding a white background
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                img = Image.alpha_composite(bg, img)
                orig_img = Image.open(newest_img_path)
                width, height = orig_img.size
                file_size = os.path.getsize(newest_img_path)
                # Always display path with Windows separators
                details_path.config(text=newest_img_path.replace('/', '\\'))  # No "Path: " prefix
                details_dim.config(text=f"Dimensions: {width} x {height}")
                details_size.config(text=f"Size: {file_size/1024:.1f} KB")
                tk_img = ImageTk.PhotoImage(img)
                img_label.config(image=tk_img)
                img_label.image = tk_img
                no_img_label.lower()
                logging.info(f'Displaying image: {newest_img_path}')
                show_last_rendered_image.last_no_img_logged = False
            except Exception as e:
                img_label.config(image="")
                img_label.image = None
                details_path.config(text="")
                details_dim.config(text="Dimensions: ")
                details_size.config(text="Size: ")
                no_img_label.lift()
                logging.error(f'Error displaying image: {e}')
        else:
            img_label.config(image="")
            img_label.image = None
            details_path.config(text="")
            details_dim.config(text="Dimensions: ")
            details_size.config(text="Size: ")
            no_img_label.lift()
            if not getattr(show_last_rendered_image, 'last_no_img_logged', False):
                logging.info('No images found in output directory')
                show_last_rendered_image.last_no_img_logged = True
        # Schedule to check again in 1 second
        root.after(1000, show_last_rendered_image)

    # Update image when output directory changes or after render
    def on_output_dir_change(*args):
        logging.info(f'Output Directory changed to: {value_entries["Output Directory"].get()}')
        root.after(200, show_last_rendered_image)
    value_entries["Output Directory"].bind("<FocusOut>", lambda e: on_output_dir_change())
    value_entries["Output Directory"].bind("<Return>", lambda e: on_output_dir_change())

    def start_render():
        logging.info('Start Render button clicked')
        # Hardcoded Daz Studio Executable Path
        daz_executable_path = os.path.join(
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            "DAZ 3D", "DAZStudio4", "DAZStudio.exe"
        )
        # Use user-writable scripts directory in %APPDATA%\Overlord\scripts
        appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
        user_scripts_dir = os.path.join(appdata, 'Overlord', 'scripts')
        os.makedirs(user_scripts_dir, exist_ok=True)
        render_script_path = os.path.join(user_scripts_dir, "masterRenderer.dsa").replace("\\", "/")

        # On first run or update, copy the script from the install dir if not present or outdated
        if getattr(sys, 'frozen', False):
            install_dir = os.path.dirname(sys.executable)
        else:
            install_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        install_script_path = os.path.join(install_dir, "scripts", "masterRenderer.dsa")
        try:
            if (not os.path.exists(render_script_path)) or (
                os.path.getmtime(install_script_path) > os.path.getmtime(render_script_path)):
                import shutil
                shutil.copy2(install_script_path, render_script_path)
                logging.info(f'Copied masterRenderer.dsa to user scripts dir: {render_script_path}')
        except Exception as e:
            logging.error(f'Could not copy masterRenderer.dsa to user scripts dir: {e}')
        # Use "Source Sets" and treat as folders
        source_sets = value_entries["Source Sets"].get("1.0", tk.END).strip().replace("\\", "/").split("\n")
        source_sets = [folder for folder in source_sets if folder]  # Remove empty lines
        source_sets = json.dumps(source_sets)
        image_output_dir = value_entries["Output Directory"].get().replace("\\", "/")
        num_instances = value_entries["Number of Instances"].get()
        log_size = value_entries["Log File Size (MBs)"].get()
        log_size = int(log_size) * 1000000  # Convert MBs to bytes
        frame_rate = value_entries["Frame Rate"].get()

        try:
            num_instances_int = int(num_instances)
        except Exception:
            num_instances_int = 1

        json_map = (
            f'{{'
            f'"num_instances": "{num_instances}", '
            f'"image_output_dir": "{image_output_dir}", '
            f'"frame_rate": "{frame_rate}", '
            f'"source_sets": {source_sets}'
            f'}}'
        )

        def run_instance():
            logging.info('Launching Daz Studio render instance')
            command = [
                daz_executable_path,
                "-scriptArg", json_map,
                "-instanceName", "#",  # Hardcoded value
                "-logSize", str(log_size),
                "-noPrompt",           # Always add -noPrompt
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
                root.after(5000, lambda: run_all_instances(i + 1))
            else:
                logging.info('All render instances launched')
                root.after(1000, show_last_rendered_image)  # Update image after render

        run_all_instances()

        # After 30 seconds, start checking for DazStudio process every 30 seconds
        # Track if Daz Studio was killed by the user
        main.dazstudio_killed_by_user = False
        def check_dazstudio_process():
            import psutil
            found = any(p.name().lower() == "dazstudio.exe" for p in psutil.process_iter(['name']))
            if not found:
                logging.info('Daz Studio is not running. Checking output directory...')
                # Only run archiveFiles.py if Daz Studio was NOT killed by the user
                if getattr(main, 'dazstudio_killed_by_user', False):
                    logging.info('Daz Studio was killed by user. Skipping archiveFiles.py.')
                    main.dazstudio_killed_by_user = False  # Reset for next run
                    return
                if not value_entries["Output Directory"].get().strip():
                    logging.error('Output Directory is empty')
                else:
                    logging.info('Output Directory contains files. Verifying contents...')
                    # Recursively check for .zip files in the output directory
                    zip_found = False
                    for rootdir, _, files in os.walk(value_entries["Output Directory"].get()):
                        for fname in files:
                            if fname.lower().endswith('.zip'):
                                zip_found = True
                    if not zip_found:
                        logging.info('No zip files found in output directory. Beginning archive process...')
                        try:
                            archive_script_path = os.path.join(install_dir, "scripts", "archiveFiles.py")
                            subprocess.Popen([
                                sys.executable,
                                archive_script_path,
                                value_entries["Output Directory"].get()
                            ])
                            logging.info(f'archiveFiles.py started with argument: {value_entries["Output Directory"].get()}')
                        except Exception as e:
                            logging.error(f'Failed to execute archiveFiles.py: {e}')
                    else:
                        logging.error('Zip files found in output directory already')
                # DazStudio is not running, add your code here
                pass
            else:
                logging.info('Daz Studio is running, checking again in 30 seconds')
                root.after(30000, check_dazstudio_process)

        root.after(30000, check_dazstudio_process)

    def end_all_daz_studio():
        logging.info('End all Daz Studio Instances button clicked')
        try:
            subprocess.Popen([
                "powershell",
                "-Command",
                'Get-Process -Name "DAZStudio" -ErrorAction SilentlyContinue | ForEach-Object { $_.Kill() }'
            ])
            main.dazstudio_killed_by_user = True
            logging.info('Kill command sent to all DAZStudio processes')
        except Exception as e:
            logging.error(f'Failed to kill DAZStudio processes: {e}')

    # Initial display
    root.after(500, show_last_rendered_image)

    button = tk.Button(root, text="Start Render", command=start_render, font=("Arial", 16, "bold"), width=20, height=2)
    button.pack(side="left", anchor="sw", padx=(30,10), pady=20)

    end_button = tk.Button(
        root,
        text="End all Daz Studio Instances",
        command=end_all_daz_studio,
        font=("Arial", 16, "bold"),
        width=26,
        height=2
    )
    end_button.pack(side="left", anchor="sw", padx=0, pady=20)

    # Run the application
    root.mainloop()

if __name__ == "__main__":
    main()

import tkinter as tk
from tkinter import filedialog
import os
import subprocess
import sys
import webbrowser

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def main():
    # Create the main window
    root = tk.Tk()
    root.title("Overlord")
    root.iconbitmap(resource_path("favicon.ico"))  # Set the application icon

    # Maximize the application window
    root.state("zoomed")

    # Load and display the logo image
    logo = tk.PhotoImage(file=resource_path("logo.png"))
    logo_label = tk.Label(root, image=logo, cursor="hand2")
    logo_label.image = logo  # Keep a reference to avoid garbage collection
    logo_label.pack(pady=10)

    # Make the logo clickable
    def open_github_link(event):
        webbrowser.open("https://github.com/Laserwolve-Games/Overlord")

    logo_label.bind("<Button-1>", open_github_link)

    # Create frames for the two tables
    file_table_frame = tk.Frame(root)
    file_table_frame.pack(pady=10, anchor="nw", side="top")  # Align left, top
    param_table_frame = tk.Frame(root)
    param_table_frame.pack(pady=10, anchor="nw", side="top")  # Directly below file_table_frame

    # File/folder path parameters
    file_params = [
        "Daz Studio Executable Path",
        "Render Script Path",
        "Source Files",
        "Output Directory"
    ]
    # Short/simple parameters
    param_params = [
        "Number of Instances",
        "Instance Naming Format",
        "Log File Size (MBs)",
        "Do not Display Prompts"
    ]
    value_entries = {}

    # File table header
    header_param = tk.Label(file_table_frame, text="Parameter Name", font=("Arial", 12, "bold"))
    header_param.grid(row=0, column=0, padx=10, pady=5)
    header_value = tk.Label(file_table_frame, text="Value", font=("Arial", 12, "bold"))
    header_value.grid(row=0, column=1, padx=10, pady=5)

    # Param table header
    header_param2 = tk.Label(param_table_frame, text="Parameter Name", font=("Arial", 12, "bold"))
    header_param2.grid(row=0, column=0, padx=10, pady=5)
    header_value2 = tk.Label(param_table_frame, text="Value", font=("Arial", 12, "bold"))
    header_value2.grid(row=0, column=1, padx=10, pady=5)

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

        if param == "Daz Studio Executable Path":
            value_entry = tk.Entry(file_table_frame, width=100, font=("Consolas", 10))
            value_entry.insert(0, r"C:\Program Files\DAZ 3D\DAZStudio4\DAZStudio.exe")
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")

            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=make_browse_file(
                    value_entry,
                    initialdir=r"C:\Program Files\DAZ 3D\DAZStudio4",
                    filetypes=(("Executable files", "*.exe"), ("All files", "*.*")),
                    title="Select DAZStudio.exe"
                )
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            value_entries[param] = value_entry

        elif param == "Render Script Path":
            value_entry = tk.Entry(file_table_frame, width=100, font=("Consolas", 10))
            value_entry.insert(0, r"C:\Users\Andrew\Documents\GitHub\DAZScripts\masterRenderer.dsa")
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")

            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=make_browse_file(
                    value_entry,
                    initialdir=r"C:\Users\Andrew\Documents\GitHub\DAZScripts",
                    filetypes=(("DAZ Script files", "*.dsa"), ("All files", "*.*")),
                    title="Select Render Script"
                )
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            value_entries[param] = value_entry

        elif param == "Source Files":
            text_widget = tk.Text(file_table_frame, width=100, height=15, font=("Consolas", 10))
            text_widget.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=make_browse_files(
                    text_widget,
                    initialdir=".",
                    filetypes=(("All files", "*.*"),),
                    title="Select Source Files"
                )
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            value_entries[param] = text_widget

        elif param == "Output Directory":
            value_entry = tk.Entry(file_table_frame, width=100, font=("Consolas", 10))
            value_entry.insert(0, r"C:/Users/Andrew/Documents/GitHub/PlainsOfShinar/spritesheets")
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")

            browse_button = tk.Button(
                file_table_frame,
                text="Browse",
                command=make_browse_folder(
                    value_entry,
                    initialdir=r"C:/Users/Andrew/Documents/GitHub/PlainsOfShinar/spritesheets",
                    title="Select Output Directory"
                )
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            value_entries[param] = value_entry

    # Short/simple parameters table
    for i, param in enumerate(param_params):
        param_label = tk.Label(param_table_frame, text=param, font=("Arial", 10), anchor="w")
        param_label.grid(row=i+1, column=0, padx=10, pady=5, sticky="w")

        if param == "Instance Naming Format":
            param_label.config(font=("Arial", 10, "underline"), fg="blue", cursor="hand2")
            param_label.bind("<Button-1>", lambda e: os.startfile("http://docs.daz3d.com/doku.php/public/software/dazstudio/4/referenceguide/tech_articles/command_line_options/application_instancing/start"))
            value_entry = tk.Entry(param_table_frame, width=5, font=("Consolas", 10))
            value_entry.insert(0, "#")
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            value_entries[param] = value_entry
        elif param == "Do not Display Prompts":
            var = tk.BooleanVar(value=True)
            value_checkbutton = tk.Checkbutton(param_table_frame, variable=var)
            value_checkbutton.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            value_entries[param] = var
        else:
            value_entry = tk.Entry(param_table_frame, width=5, font=("Consolas", 10))
            if param == "Number of Instances":
                value_entry.insert(0, "1")
            elif param == "Log File Size (MBs)":
                value_entry.insert(0, "500")
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            value_entries[param] = value_entry

    def start_render():
        daz_executable_path = value_entries["Daz Studio Executable Path"].get()
        render_script_path = value_entries["Render Script Path"].get().replace("\\", "/")
        source_files = value_entries["Source Files"].get("1.0", tk.END).strip().replace("\\", "/")
        output_dir = value_entries["Output Directory"].get().replace("\\", "/")
        num_instances = value_entries["Number of Instances"].get()
        instance_name = value_entries["Instance Naming Format"].get()
        log_size = value_entries["Log File Size (MBs)"].get()
        log_size = int(log_size) * 1000000  # Convert MBs to bytes
        prompt_var = value_entries["Do not Display Prompts"].get()

        command = [
            daz_executable_path,
            "-scriptArg", str(num_instances),
            "-scriptArg", str(output_dir),
            "-scriptArg", str(source_files),
            "-instanceName", str(instance_name),
            "-logSize", str(log_size),
        ]
        if prompt_var:
            command.append("-noPrompt")
        command.append(render_script_path)

        subprocess.Popen(command)

    button = tk.Button(root, text="Start Render", command=start_render)
    button.pack(side="bottom", pady=20)

    # Run the application
    root.mainloop()

if __name__ == "__main__":
    main()

import tkinter as tk
from tkinter import filedialog
import os
import subprocess
import sys

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

    # Disable window resizing
    root.resizable(False, False)

    # Set the window size
    root.geometry("800x800")

    # Load and display the logo image
    logo = tk.PhotoImage(file=resource_path("logo.png"))
    logo_label = tk.Label(root, image=logo)
    logo_label.image = logo  # Keep a reference to avoid garbage collection
    logo_label.pack(pady=10)

    # Create a frame for the table
    table_frame = tk.Frame(root)
    table_frame.pack(pady=10)

    # Create the table header
    header_param = tk.Label(table_frame, text="Parameter Name", font=("Arial", 12, "bold"))
    header_param.grid(row=0, column=0, padx=10, pady=5)
    header_value = tk.Label(table_frame, text="Value", font=("Arial", 12, "bold"))
    header_value.grid(row=0, column=1, padx=10, pady=5)

    # Parameter names
    params = [
        "Daz Studio Executable Path",
        "Render Script Path",
        "Number of Instances",
        "Instance Naming Format",
        "Log File Size (MBs)",
        "Do not Display Prompts"
    ]
    value_entries = {}

    # Add rows to the table
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

    for i, param in enumerate(params):
        param_label = tk.Label(table_frame, text=param, font=("Arial", 10), anchor="w")
        param_label.grid(row=i+1, column=0, padx=10, pady=5, sticky="w")

        if param == "Daz Studio Executable Path":
            value_entry = tk.Entry(table_frame, width=40)
            value_entry.insert(0, r"C:\Program Files\DAZ 3D\DAZStudio4\DAZStudio.exe")
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")

            browse_button = tk.Button(
                table_frame,
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
            value_entry = tk.Entry(table_frame, width=40)
            value_entry.insert(0, r"C:\Users\Andre\OneDrive\repositories\DAZScripts\masterRenderer.dsa")
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")

            browse_button = tk.Button(
                table_frame,
                text="Browse",
                command=make_browse_file(
                    value_entry,
                    initialdir=r"C:\Users\Andre\OneDrive\repositories\DAZScripts",
                    filetypes=(("DAZ Script files", "*.dsa"), ("All files", "*.*")),
                    title="Select Render Script"
                )
            )
            browse_button.grid(row=i+1, column=2, padx=5, pady=5)
            value_entries[param] = value_entry

        elif param == "Instance Naming Format":
            param_label.config(font=("Arial", 10, "underline"), fg="blue", cursor="hand2")
            param_label.bind("<Button-1>", lambda e: os.startfile("http://docs.daz3d.com/doku.php/public/software/dazstudio/4/referenceguide/tech_articles/command_line_options/application_instancing/start"))
            value_entry = tk.Entry(table_frame, width=10)
            value_entry.insert(0, "#")
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            value_entries[param] = value_entry
        elif param == "Do not Display Prompts":
            var = tk.BooleanVar(value=True)
            value_checkbutton = tk.Checkbutton(table_frame, variable=var)
            value_checkbutton.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            value_entries[param] = var
        else:
            value_entry = tk.Entry(table_frame, width=10)
            if param == "Number of Instances":
                value_entry.insert(0, "1")
            elif param == "Log File Size (MBs)":
                value_entry.insert(0, "500")
            value_entry.grid(row=i+1, column=1, padx=10, pady=5, sticky="e")
            value_entries[param] = value_entry

    def start_render():
        daz_executable_path = value_entries["Daz Studio Executable Path"].get()
        render_script_path = value_entries["Render Script Path"].get().replace("\\", "/")
        num_instances = value_entries["Number of Instances"].get()
        instance_name = value_entries["Instance Naming Format"].get()
        log_size = value_entries["Log File Size (MBs)"].get()
        log_size = int(log_size) * 1000000  # Convert MBs to bytes
        prompt_var = value_entries["Do not Display Prompts"].get()

        command = [
            daz_executable_path,
            "-scriptArg", str(num_instances),
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

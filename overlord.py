import tkinter as tk

def main():
    # Create the main window
    root = tk.Tk()
    root.title("Overlord")
    root.iconbitmap("favicon.ico")  # Set the application icon

    # Disable window resizing
    root.resizable(False, False)

    # Set the window size
    root.geometry("400x800")

    # Load and display the logo image
    logo = tk.PhotoImage(file="logo.png")
    logo_label = tk.Label(root, image=logo)
    logo_label.image = logo  # Keep a reference to avoid garbage collection
    logo_label.pack(pady=10)

    # Create a label widget
    label = tk.Label(root, text="Hello, World!", font=("Arial", 16))
    label.pack(pady=20)

    # Run the application
    root.mainloop()

if __name__ == "__main__":
    main()

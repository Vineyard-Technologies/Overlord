import subprocess
import sys

def main():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--noconsole",
        "--icon", "images/favicon.ico",
        "--add-data", "images/favicon.ico:images",
        "--add-data", "images/overlordLogo.png:images",
        "--add-data", "images/laserwolveGamesLogo.png:images",
        "src/overlord.py"
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("PyInstaller build failed.", file=sys.stderr)
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()

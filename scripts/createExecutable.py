import subprocess
import sys

def main():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--noconsole",
        "--icon", "assets/favicon.ico",
        "--add-data", "assets/favicon.ico:assets",
        "--add-data", "assets/overlordLogo.png:assets",
        "--add-data", "assets/laserwolveGamesLogo.png:assets",
        "src/overlord.py"
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("PyInstaller build failed.", file=sys.stderr)
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()

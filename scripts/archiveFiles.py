import os
import sys
import zipfile
import re
from pathlib import Path
import logging

# Copy of setup_logger from overlord.py
def setup_logger():
    appdata = os.environ.get('APPDATA')
    if appdata:
        log_dir = os.path.join(appdata, 'Overlord')
    else:
        log_dir = os.path.join(os.path.expanduser('~'), 'Overlord')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'log.txt')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[logging.FileHandler(log_path, encoding='utf-8'), logging.StreamHandler()]
    )
    logging.info(f'--- archiveFiles.py started --- (log file: {log_path})')

def get_default_output_dir():
    from pathlib import Path
    import getpass
    user = getpass.getuser()
    downloads = Path.home() / 'Downloads'
    return downloads / 'output'

def main():

    setup_logger()
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1])
        logging.info(f"Using directory from argument: {target_dir}")
    else:
        target_dir = get_default_output_dir()
        logging.info(f"No directory argument provided. Using default: {target_dir}")
    if not target_dir.exists() or not target_dir.is_dir():
        logging.error(f"Target directory {target_dir} does not exist or is not a directory.")
        return

    # Recursively walk through all files in target_dir and subdirectories
    all_files = []
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            file_path = Path(root) / file
            all_files.append(file_path)
    logging.info(f"Found {len(all_files)} files in {target_dir} and subfolders.")

    pattern = re.compile(r'^(.*?)_([^_]+)_(.*?)\.[^\.]+$')
    groups = {}
    for file_path in all_files:
        file = file_path.name
        m = pattern.match(file)
        if m:
            prefix, middle, suffix = m.groups()
            archive_name = f"{prefix}_{middle}.zip"
            if archive_name not in groups:
                groups[archive_name] = []
            groups[archive_name].append(file_path)
            logging.info(f"Grouping file {file_path} into archive {archive_name}")
        else:
            logging.info(f"File {file_path} does not match pattern, skipping.")

    for archive_name, file_paths in groups.items():
        # Place the archive in the same directory as the first file in the group
        first_file = file_paths[0]
        archive_dir = first_file.parent
        archive_path = archive_dir / archive_name
        logging.info(f"Creating archive {archive_path} with {len(file_paths)} files.")
        # Use a set to avoid duplicate filenames in the archive
        seen_filenames = set()
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_STORED) as zf:
            for file_path in file_paths:
                arcname = file_path.name
                if arcname in seen_filenames:
                    continue
                seen_filenames.add(arcname)
                zf.write(file_path, arcname=arcname)
                os.remove(file_path)
                logging.info(f"Archived and deleted {file_path}")
        logging.info(f"Created {archive_path} with {len(seen_filenames)} files.")

if __name__ == "__main__":
    main()
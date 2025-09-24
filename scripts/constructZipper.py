import os
import zipfile
import re
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

def parse_filename(filename):
    """
    Parse a filename to extract the components needed for organization.
    Expected format: prefix-action_rotation-sequence.extension
    Example: woman_shadow-powerUp_-67.5-014.webp
    Returns: (prefix, action, rotation_part, full_stem)
    """
    # Remove extension
    stem = Path(filename).stem
    
    # Pattern to match: prefix-action_rotation-sequence
    # This handles cases like: woman_shadow-powerUp_-67.5-014
    pattern = r'^([^-]+)-([^_]+)_(.+)-\d+$'
    match = re.match(pattern, stem)
    
    if match:
        prefix = match.group(1)  # woman_shadow
        action = match.group(2)  # powerUp
        rotation_part = match.group(3)  # -67.5
        
        # Create the base name without sequence number
        base_name = f"{prefix}-{action}_{rotation_part}"
        
        return prefix, action, base_name
    else:
        # Fallback for files that don't match expected pattern
        parts = stem.split('-')
        if len(parts) >= 2:
            prefix = parts[0]
            action = parts[1].split('_')[0] if '_' in parts[1] else parts[1]
            return prefix, action, stem
        else:
            return stem, "unknown", stem

def create_zip_archive(args):
    """
    Create a single zip archive from a group of files.
    This function is designed to be run in a separate thread.
    """
    base_name, files, output_path = args
    
    if not files:
        return None
        
    # Use the first file's metadata for folder structure
    first_file = files[0]
    prefix = first_file['prefix']
    action = first_file['action']
    
    # Create directory structure: ConstructZips/prefix/action/
    target_dir = output_path / prefix / action
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Create zip file: action_rotation.zip (without prefix)
    # Extract action and rotation from base_name (format: prefix-action_rotation)
    action_rotation = base_name.split('-', 1)[1] if '-' in base_name else base_name
    zip_path = target_dir / f"{action_rotation}.zip"
    
    try:
        # Create or update the zip file
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_info in files:
                file_path = file_info['file_path']
                # Add file to zip with just its filename (not full path)
                zip_file.write(file_path, file_path.name)
        
        return f"Created {zip_path} with {len(files)} files"
    except Exception as e:
        return f"Error creating {zip_path}: {str(e)}"

def organize_files(source_dir, output_base_dir, max_workers=None):
    """
    Organize files from source_dir into folders and zip archives in output_base_dir.
    Uses multithreading to speed up the zip creation process.
    
    Args:
        source_dir: Source directory containing files to organize
        output_base_dir: Base directory for output
        max_workers: Maximum number of threads to use (None = auto-detect)
    """
    source_path = Path(source_dir)
    output_path = Path(output_base_dir) / "ConstructZips"
    
    if not source_path.exists():
        print(f"Source directory does not exist: {source_dir}")
        return
    
    # Group files by their base name (without sequence number)
    file_groups = defaultdict(list)
    
    print("Scanning files...")
    # Scan all files in the source directory
    for file_path in source_path.iterdir():
        if file_path.is_file():
            prefix, action, base_name = parse_filename(file_path.name)
            file_groups[base_name].append({
                'file_path': file_path,
                'prefix': prefix,
                'action': action,
                'base_name': base_name
            })
    
    print(f"Found {len(file_groups)} unique file groups")
    
    # Prepare arguments for multithreaded processing
    zip_tasks = []
    for base_name, files in file_groups.items():
        zip_tasks.append((base_name, files, output_path))
    
    # Use ThreadPoolExecutor for multithreaded processing
    if max_workers is None:
        max_workers = min(32, (os.cpu_count() or 1) + 4)  # Default ThreadPoolExecutor logic
    
    print(f"Processing {len(zip_tasks)} zip archives using {max_workers} threads...")
    
    completed_count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {executor.submit(create_zip_archive, task): task for task in zip_tasks}
        
        # Process completed tasks
        for future in as_completed(future_to_task):
            result = future.result()
            if result:
                print(result)
                completed_count += 1
                if completed_count % 50 == 0:  # Progress update every 50 files
                    print(f"Progress: {completed_count}/{len(zip_tasks)} archives completed")
    
    print(f"Completed processing {completed_count} zip archives")

def main():
    """
    Main function to organize files.
    """
    # Get the current user's Downloads folder dynamically
    downloads_path = Path.home() / "Downloads"
    source_directory = downloads_path / "output"
    
    print("Starting file organization...")
    print(f"Source directory: {source_directory}")
    
    organize_files(source_directory, source_directory)
    
    print("File organization complete!")

if __name__ == "__main__":
    main()
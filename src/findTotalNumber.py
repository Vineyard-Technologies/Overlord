import sys
import json
import os

def find_total_images(source_sets):
    total_frames = 0
    for set_dir in source_sets:
        for root, dirs, files in os.walk(set_dir):
            for fname in files:
                if '_animation.duf' in fname:
                    try:
                        fpath = os.path.join(root, fname)
                        with open(fpath, 'r', encoding='utf-8') as f:
                            # Try to find the JSON part with scene.animations
                            content = f.read()
                            # Find the start of the JSON (skip DAZ header if present)
                            json_start = content.find('{')
                            if json_start == -1:
                                continue
                            data = json.loads(content[json_start:])
                            animations = data.get('scene', {}).get('animations', [])
                            for anim in animations:
                                keys = anim.get('keys', [])
                                total_frames += len(keys)
                    except Exception:
                        continue
    return total_frames

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(0)
        sys.exit(0)
    try:
        # Expecting a JSON-encoded list of source set directories as the first argument
        source_sets = json.loads(sys.argv[1])
        total = find_total_images(source_sets)
        print(total)
    except Exception:
        print(0)

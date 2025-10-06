import subprocess
import json
# We weren't able to create this script in Batch or PowerShell.
# I think it's because of the fact that the total length of the command is over 256 characters.
script_args = {
    "num_instances": "1",
    "image_output_dir": "C:/Users/Andrew/Downloads/output",
    "frame_rate": "30",
    "subject_file": "C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/sets/woman/woman.duf",
    "animations": [
        "C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/sets/woman/block.duf",
        "C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/sets/woman/die.duf",
        "C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/sets/woman/downwardSlash.duf",
        "C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/sets/woman/hit.duf",
        "C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/sets/woman/idle.duf",
        "C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/sets/woman/pommelStrike.duf",
        "C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/sets/woman/powerUp.duf",
        "C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/sets/woman/run.duf",
        "C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/sets/woman/sweep.duf",
        "C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/sets/woman/walk.duf"
    ],
    "prop_animations": [],
    "gear": ["C:/Users/Andrew/Documents/GitHub/DataLake/Overlord/gear/leatherJacket.duf"],
    "gear_animations": [],
    "template_path": "c:/Users/Andrew/Documents/GitHub/Overlord/templates/masterTemplate.duf",
    "render_shadows": True,
    "results_directory_path": "C:/Users/Andrew/AppData/Local/Overlord/IrayServer/results/admin",
    "cache_db_size_threshold_gb": "10"
}

command = [
    'C:\\Program Files\\DAZ 3D\\DAZStudio4\\DAZStudio.exe',
    '-scriptArg',
    json.dumps(script_args),
    '-instanceName',
    '#',
    '-logSize',
    '100000000',
    '-headless',
    '-noPrompt',
    'c:/Users/Andrew/Documents/GitHub/Overlord/scripts/masterRenderer.dsa'
]

print("running command...")
subprocess.Popen(command)
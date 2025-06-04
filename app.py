import os
import json
import random
import zipfile
import logging
import uuid
import hashlib
from io import BytesIO
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from rtonlib import RTONParser

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize RTON parser
rton_parser = RTONParser()

# Plant pools for content modifications
PLANT_POOL = [
    "peashooter", "sunflower", "cherryBomb", "wallNut", "potato", "snowPea",
    "chomper", "repeater", "puffShroom", "sunShroom", "fumeShroom", "graveShroom",
    "hypnoShroom", "scaredyShroom", "iceShroom", "doomShroom", "lilyPad", "squash",
    "threepeater", "tanglekelp", "jalapeño", "spikeweed", "torchwood", "tallNut",
    "seaShroom", "plantern", "cactus", "blover", "splitPea", "starfruit",
    "pumpkin", "magnetShroom", "cabbagePult", "flowerPot", "kernelPult", "coffeeBean",
    "garlic", "umbrellaLeaf", "marigold", "melonPult", "gatlingPea", "twinSunflower",
    "gloomShroom", "cattail", "winterMelon", "goldMagnet", "spikerock", "cobCannon"
]

GRID_OBJECTS = [
    {"type": "plant", "items": ["wallNut", "sunflower", "peashooter", "snowPea"]},
    {"type": "tile", "items": ["gold", "power", "ice", "fire"]},
    {"type": "obstacle", "items": ["rock", "tombstone", "water"]}
]

def get_rton_files():
    """Get all .rton files from the levelstoshuffle directory"""
    levels_dir = Path("levelstoshuffle")
    if not levels_dir.exists():
        levels_dir.mkdir(exist_ok=True)
        return []
    
    return list(levels_dir.glob("*.rton"))

def parse_level_filename(filename):
    """Parse level filename to extract world and number"""
    import re
    
    # Remove .rton extension
    base_name = filename.replace('.rton', '')
    
    # Match pattern like "world123" or "world123_suffix"
    match = re.match(r'^([a-zA-Z]+)(\d+)(?:_.*)?$', base_name)
    if match:
        world = match.group(1).lower()
        number = int(match.group(2))
        return world, number
    
    return None, None

def create_filename_groups(files, same_world_only=False, number_range=None):
    """Group files for intelligent shuffling"""
    groups = {}
    
    for file_path in files:
        filename = file_path.name
        world, number = parse_level_filename(filename)
        
        if world is None or number is None:
            # Handle files that don't match pattern
            groups.setdefault('other', []).append(file_path)
            continue
        
        if same_world_only:
            # Group by world only
            groups.setdefault(world, []).append(file_path)
        elif number_range:
            # Group by number range within each world
            range_start = max(1, number - number_range)
            range_end = number + number_range
            key = f"{world}_{range_start}-{range_end}"
            groups.setdefault(key, []).append(file_path)
        else:
            # Default: all files together
            groups.setdefault('all', []).append(file_path)
    
    return groups

def shuffle_within_groups(groups, seed=None):
    """Shuffle filenames within each group using optional seed"""
    shuffled_mapping = {}
    
    # Create a seeded random instance if seed is provided
    if seed:
        # Create a hash of the seed for consistency
        seed_hash = hashlib.sha256(str(seed).encode()).hexdigest()
        # Use first 8 characters as integer seed
        numeric_seed = int(seed_hash[:8], 16)
        rng = random.Random(numeric_seed)
    else:
        rng = random
    
    for group_name, files in groups.items():
        if len(files) <= 1:
            # No shuffling needed for single files
            for file_path in files:
                shuffled_mapping[file_path] = file_path.name
            continue
        
        # Get original filenames
        original_names = [f.name for f in files]
        shuffled_names = original_names.copy()
        
        # Use seeded shuffle for consistent results
        rng.shuffle(shuffled_names)
        
        # Create mapping
        for file_path, new_name in zip(files, shuffled_names):
            shuffled_mapping[file_path] = new_name
    
    return shuffled_mapping

@app.route('/')
def index():
    """Main page"""
    files = get_rton_files()
    return render_template('index.html', file_count=len(files))

@app.route('/process', methods=['POST'])
def process_files():
    """Process the files with selected shuffling options"""
    files = get_rton_files()
    
    if not files:
        flash('No .rton files found in levelstoshuffle directory!', 'error')
        return redirect(url_for('index'))
    
    # Get shuffling options from form
    same_world_only = 'same_world_only' in request.form
    number_range_enabled = 'number_range' in request.form
    shuffle_seed = request.form.get('shuffle_seed', '').strip()
    number_range = 5  # 5 numbers on either side
    
    # Create filename groups based on options
    if same_world_only and number_range_enabled:
        groups = create_filename_groups(files, same_world_only=True, number_range=number_range)
    elif same_world_only:
        groups = create_filename_groups(files, same_world_only=True)
    elif number_range_enabled:
        groups = create_filename_groups(files, number_range=number_range)
    else:
        groups = create_filename_groups(files)
    
    # Shuffle within groups using seed if provided
    filename_mapping = shuffle_within_groups(groups, shuffle_seed)
    
    # Create ZIP file in memory
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Process each file
        for original_file in files:
            try:
                new_name = filename_mapping[original_file]
                
                # Read original file (no content modifications, just filename shuffling)
                with open(original_file, 'rb') as f:
                    file_data = f.read()
                
                # Add file to ZIP with new name
                zip_file.writestr(new_name, file_data)
                
            except Exception as e:
                app.logger.error(f"Error processing {original_file.name}: {str(e)}")
        
        # Add log file with basic info (no DB logs)
        log_content = (
            f"Processed {len(files)} files\n"
            f"Seed: {shuffle_seed if shuffle_seed else 'Random (no seed)'}\n"
            f"Same world only: {same_world_only}\n"
            f"Number range enabled: {number_range_enabled} (±{number_range})\n"
        )
        zip_file.writestr("shuffle_log.txt", log_content)
    
    zip_buffer.seek(0)
    
    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name='shuffled_levels.zip',
        mimetype='application/zip'
    )

@app.route('/download-original-levels')
def download_original_levels():
    """Download original level files as ZIP"""
    files = get_rton_files()
    
    if not files:
        flash('No .rton files found in levelstoshuffle directory!', 'error')
        return redirect(url_for('index'))
    
    try:
        # Create ZIP file in memory
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add all original files
            for file_path in files:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                zip_file.writestr(file_path.name, file_data)
            
            # Add installation instructions
            instructions = """PvZ2 Level Installation Instructions

To install these level files on Android:

1. Ensure your device is rooted or you have file manager access to app data
2. Navigate to: Android/data/com.ea.game.pvz2_row/files/No_Backup/C.D.XX.X/levels
   (Replace C.D.XX.X with your actual game version folder)
3. Backup your original levels folder first!
4. Copy all .rton files from this ZIP to the levels folder
5. Restart Plants vs Zombies 2

Note: Game version folders vary (e.g., C.D.10.1.1, C.D.9.8.1, etc.)
Always backup original files before replacing them.
Modifying game files may void warranties and could cause issues.

For iOS or PC versions, locate the equivalent levels directory in your game installation.
"""
            zip_file.writestr("INSTALLATION_INSTRUCTIONS.txt", instructions)
        
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name='original_levels.zip',
            mimetype='application/zip'
        )
        
    except Exception as e:
        flash(f'Error creating original levels ZIP: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/status')
def status():
    """Get current status of files"""
    files = get_rton_files()
    
    # Check for pp.dat files
    pp_files_available = {}
    for i in range(1, 4):
        pp_path = Path(f"recommendeddats/pp{i}.dat")
        pp_files_available[i] = pp_path.exists()
    
    return jsonify({
        'file_count': len(files),
        'files': [f.name for f in files[:10]],  # First 10 files for preview
        'pp_files': pp_files_available,
        'database_stats': 'Disabled - no database in this version'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

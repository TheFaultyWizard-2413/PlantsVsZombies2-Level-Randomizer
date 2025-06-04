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
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from rtonlib import RTONParser


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    # Fix postgres:// to postgresql:// for SQLAlchemy compatibility
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Initialize the app with the extension
db.init_app(app)

# Initialize RTON parser
rton_parser = RTONParser()

# Create database tables
with app.app_context():
    # Make sure to import the models here or their tables won't be created
    import models  # noqa: F401
    db.create_all()

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
    
    # Generate seed hash if seed is provided
    seed_hash = None
    if shuffle_seed:
        seed_hash = hashlib.sha256(shuffle_seed.encode()).hexdigest()
    
    # Create new shuffle session
    from models import ShuffleSession, FileMapping
    session_id = str(uuid.uuid4())
    
    shuffle_session = ShuffleSession(
        session_id=session_id,
        file_count=len(files),
        same_world_only=same_world_only,
        number_range_enabled=number_range_enabled,
        seed=shuffle_seed if shuffle_seed else None,
        seed_hash=seed_hash
    )
    db.session.add(shuffle_session)
    
    # Create log for tracking changes
    log_entries = []
    log_entries.append(f"Processing {len(files)} .rton files")
    log_entries.append(f"Session ID: {session_id}")
    log_entries.append(f"Seed: {shuffle_seed if shuffle_seed else 'Random (no seed)'}")
    log_entries.append(f"Same world only: {same_world_only}")
    log_entries.append(f"Number range shuffling: {number_range_enabled} (±{number_range} if enabled)")
    log_entries.append("-" * 50)
    
    # Create filename groups based on options
    if same_world_only and number_range_enabled:
        groups = create_filename_groups(files, same_world_only=True, number_range=number_range)
        log_entries.append("Shuffling: Same world + number range (±5)")
    elif same_world_only:
        groups = create_filename_groups(files, same_world_only=True)
        log_entries.append("Shuffling: Same world only")
    elif number_range_enabled:
        groups = create_filename_groups(files, number_range=number_range)
        log_entries.append("Shuffling: Number range across all worlds (±5)")
    else:
        groups = create_filename_groups(files)
        log_entries.append("Shuffling: Completely random")
    
    # Log groups
    log_entries.append(f"\nCreated {len(groups)} shuffle groups:")
    for group_name, group_files in groups.items():
        log_entries.append(f"  {group_name}: {len(group_files)} files")
    log_entries.append("")
    
    # Shuffle within groups using seed if provided
    filename_mapping = shuffle_within_groups(groups, shuffle_seed)
    
    # Log filename swaps and save to database (batch insert to avoid parameter limit)
    log_entries.append("FILENAME SHUFFLES:")
    file_mappings = []
    
    for original_file, new_name in filename_mapping.items():
        if original_file.name != new_name:
            log_entries.append(f"{original_file.name} -> {new_name}")
        
        # Parse file information for database
        world, level_number = parse_level_filename(original_file.name)
        
        # Prepare file mapping for batch insert
        file_mappings.append({
            'session_id': session_id,
            'original_filename': original_file.name,
            'shuffled_filename': new_name,
            'world': world,
            'level_number': level_number
        })
    
    # Batch insert file mappings to avoid parameter limit
    try:
        if file_mappings:
            db.session.execute(
                FileMapping.__table__.insert(),
                file_mappings
            )
    except Exception as e:
        app.logger.error(f"Failed to batch insert file mappings: {e}")
    
    log_entries.append("")
    
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
                log_entries.append(f"Error processing {original_file.name}: {str(e)}")
                app.logger.error(f"Error processing {original_file.name}: {str(e)}")
        
        # Add log file
        log_content = "\n".join(log_entries)
        zip_file.writestr("shuffle_log.txt", log_content)
    
    # Commit database changes
    try:
        db.session.commit()
        app.logger.info(f"Saved shuffle session {session_id} to database")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Failed to save session to database: {e}")
    
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

@app.route('/download-pp/<int:option>')
def download_pp_dat(option):
    """Download recommended pp.dat files"""
    if option not in [1, 2, 3]:
        flash('Invalid pp.dat option selected!', 'error')
        return redirect(url_for('index'))
    
    # Map to file paths
    pp_files = {
        1: Path("recommendeddats/pp1.dat"),
        2: Path("recommendeddats/pp2.dat"), 
        3: Path("recommendeddats/pp3.dat")
    }
    
    file_path = pp_files[option]
    
    if not file_path.exists():
        flash(f'pp{option}.dat file not found! Please add it to the recommendeddats directory.', 'error')
        return redirect(url_for('index'))
    
    # Log download to database
    from models import DownloadLog
    try:
        download_log = DownloadLog(
            pp_option=option,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:500]  # Limit length
        )
        db.session.add(download_log)
        db.session.commit()
        app.logger.info(f"Logged pp{option}.dat download from {request.remote_addr}")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Failed to log download: {e}")
    
    try:
        return send_file(
            file_path,
            as_attachment=True,
            download_name='pp.dat',
            mimetype='application/octet-stream'
        )
    except Exception as e:
        flash(f'Error downloading pp.dat: {str(e)}', 'error')
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
    
    # Get database statistics
    from models import ShuffleSession, DownloadLog
    try:
        total_sessions = db.session.query(ShuffleSession).count()
        total_downloads = db.session.query(DownloadLog).count()
        recent_sessions = db.session.query(ShuffleSession).order_by(ShuffleSession.timestamp.desc()).limit(5).all()
        
        stats = {
            'total_shuffle_sessions': total_sessions,
            'total_pp_downloads': total_downloads,
            'recent_sessions': [
                {
                    'timestamp': session.timestamp.isoformat(),
                    'file_count': session.file_count,
                    'same_world_only': session.same_world_only,
                    'number_range_enabled': session.number_range_enabled
                } for session in recent_sessions
            ]
        }
    except Exception as e:
        app.logger.error(f"Failed to get database stats: {e}")
        stats = {'error': 'Database unavailable'}
    
    return jsonify({
        'file_count': len(files),
        'files': [f.name for f in files[:10]],  # First 10 files for preview
        'pp_files': pp_files_available,
        'database_stats': stats
    })

@app.route('/admin')
def admin_dashboard():
    """Simple admin dashboard for viewing statistics"""
    from models import ShuffleSession, DownloadLog, FileMapping
    
    try:
        # Get statistics
        total_sessions = db.session.query(ShuffleSession).count()
        total_downloads = db.session.query(DownloadLog).count()
        total_file_mappings = db.session.query(FileMapping).count()
        
        # Recent sessions
        recent_sessions = db.session.query(ShuffleSession).order_by(ShuffleSession.timestamp.desc()).limit(10).all()
        
        # Download stats by pp.dat type
        download_stats = db.session.query(
            DownloadLog.pp_option,
            db.func.count(DownloadLog.id).label('count')
        ).group_by(DownloadLog.pp_option).all()
        
        return render_template('admin.html',
                             total_sessions=total_sessions,
                             total_downloads=total_downloads,
                             total_file_mappings=total_file_mappings,
                             recent_sessions=recent_sessions,
                             download_stats=download_stats)
    
    except Exception as e:
        app.logger.error(f"Admin dashboard error: {e}")
        return render_template('admin.html', error=str(e))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

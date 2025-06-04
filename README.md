# PvZ2 Level Shuffler

A Flask-based web application that shuffles Plants vs Zombies 2 level filenames with intelligent grouping options and provides downloadable player profile files.

## Features

### 🎯 Intelligent Level Shuffling
- **Seed-based randomization**: Use custom seeds for reproducible shuffles
- **Same World Only**: Beach levels only swap with other beach levels
- **Number Range (±5)**: Level 8 can only swap with levels 3-13
- **Combination options**: Mix same world and number range restrictions

### 📦 Downloads
- **Shuffled Levels**: ZIP file with shuffled level filenames and detailed log
- **Original Levels**: Unmodified level files with installation instructions
- **PP.dat Files**: Three balanced player profile options:
  - Balanced Start: Basic plants, 1000 coins, 100 gems (recommended)
  - Enhanced Start: Basic plants, 3000 coins, 300 gems
  - Premium Start: Basic plants, 10000 coins, 1000 gems, 500 mints

### 📊 Database & Analytics
- PostgreSQL database tracking all shuffle sessions
- Download statistics for PP.dat files
- Admin dashboard at `/admin`
- Session history with seed tracking

## Installation

### Prerequisites
- Python 3.11+
- PostgreSQL database
- Flask and related dependencies

### Setup

1. Clone the repository:
```bash
git clone <your-repo-url>
cd pvz2-level-shuffler
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
export SESSION_SECRET="your-secret-key"
```

4. Add level files:
   - Place your .rton level files in the `levelstoshuffle/` directory
   - Add PP.dat files in `recommendeddats/` (pp1.dat, pp2.dat, pp3.dat)

5. Run the application:
```bash
python main.py
```

The application will be available at `http://localhost:5000`

## File Structure

```
pvz2-level-shuffler/
├── app.py                 # Main Flask application
├── main.py               # Application entry point
├── models.py             # Database models
├── rtonlib.py            # RTON file parser
├── templates/
│   ├── index.html        # Main interface
│   └── admin.html        # Admin dashboard
├── static/
│   └── style.css         # Custom styling
├── levelstoshuffle/      # Place .rton level files here
├── recommendeddats/      # Place PP.dat files here
└── requirements.txt      # Python dependencies
```

## Usage

### Shuffling Levels

1. **Choose a seed** (optional): Enter any text/number for reproducible results
2. **Select shuffling options**:
   - Same World Only: Keep levels within their worlds
   - Number Range (±5): Limit swaps to nearby level numbers
3. **Process files**: Download the shuffled ZIP with log file

### Installing Modified Levels

#### Android
1. Root access or file manager with app data access required
2. Navigate to: `Android/data/com.ea.game.pvz2_row/files/No_Backup/C.D.XX.X/levels`
3. Backup original files first
4. Copy .rton files from downloaded ZIP
5. Restart Plants vs Zombies 2

#### iOS/PC
Locate the equivalent levels directory in your game installation.

### PP.dat Installation

Place the downloaded pp.dat file in your game's player profile directory, typically alongside the levels folder.

## API Endpoints

- `GET /` - Main interface
- `POST /process` - Process level files with options
- `GET /download-original-levels` - Download original level files
- `GET /download-pp/<int:option>` - Download PP.dat files (1-3)
- `GET /status` - Get file counts and statistics
- `GET /admin` - Admin dashboard

## Database Schema

### Tables
- `shuffle_session` - Track shuffle operations with seeds and options
- `file_mapping` - Individual file mappings within sessions
- `download_log` - PP.dat download tracking

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Technical Details

### Seed-based Randomization
Uses SHA256 hashing of user input to create deterministic random seeds, ensuring identical shuffles across different runs and users.

### File Processing
- Parses level filenames to extract world and level numbers
- Groups files based on user-selected criteria
- Applies deterministic shuffling within groups
- Preserves original file content (filename-only shuffling)

### Database Integration
- Tracks all shuffle sessions with metadata
- Logs file mappings for audit trails
- Monitors PP.dat download patterns
- Provides analytics through admin dashboard

## License

This project is for educational and modding purposes. Plants vs Zombies 2 is owned by Electronic Arts.

## Disclaimer

Modifying game files may void warranties and could cause issues. Always backup original files before applying modifications.
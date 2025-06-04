from app import db
from datetime import datetime

class ShuffleSession(db.Model):
    """Track shuffle sessions and their configurations"""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    file_count = db.Column(db.Integer, nullable=False)
    same_world_only = db.Column(db.Boolean, default=False)
    number_range_enabled = db.Column(db.Boolean, default=False)
    download_count = db.Column(db.Integer, default=0)
    seed = db.Column(db.String(255))  # Store the randomization seed
    seed_hash = db.Column(db.String(64))  # Hash of seed for quick lookups
    
    def __repr__(self):
        return f'<ShuffleSession {self.session_id}>'

class FileMapping(db.Model):
    """Track individual file mappings within shuffle sessions"""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('shuffle_session.session_id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    shuffled_filename = db.Column(db.String(255), nullable=False)
    world = db.Column(db.String(50))
    level_number = db.Column(db.Integer)
    
    def __repr__(self):
        return f'<FileMapping {self.original_filename} -> {self.shuffled_filename}>'

class DownloadLog(db.Model):
    """Track pp.dat downloads"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    pp_option = db.Column(db.Integer, nullable=False)  # 1, 2, or 3
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    user_agent = db.Column(db.Text)
    
    def __repr__(self):
        return f'<DownloadLog pp{self.pp_option}.dat at {self.timestamp}>'
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class StudentRequest(db.Model):
    __tablename__ = 'student_request'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    adresse = db.Column(db.Text, nullable=False)
    telephone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    
    # NOUVEAU : Région universitaire
    region_universitaire = db.Column(db.String(100), nullable=False, default='Dakar')
    
    # File paths for uploaded documents
    certificat_inscription = db.Column(db.String(300))
    certificat_residence = db.Column(db.String(300))
    demande_manuscrite = db.Column(db.String(300))
    carte_membre_reed = db.Column(db.String(300))
    copie_cni = db.Column(db.String(300))
    
    # Status: pending, approved, rejected
    status = db.Column(db.String(20), default='pending')
    
    # Timestamps
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)
    date_processed = db.Column(db.DateTime)
    
    # Admin notes
    admin_notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<StudentRequest {self.nom} {self.prenom}>'
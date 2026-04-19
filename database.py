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
    
    # NOUVEAU : Établissement (texte libre)
    etablissement = db.Column(db.String(200), nullable=False, default='')
    
    # Catégorie: eleve ou etudiant
    categorie = db.Column(db.String(20), nullable=False, default='etudiant')
    
    # Type de demande: logement ou bourse
    request_type = db.Column(db.String(20), nullable=False, default='logement')
    
    # File paths for uploaded documents (logement)
    certificat_inscription = db.Column(db.String(300))
    certificat_residence = db.Column(db.String(300))
    demande_manuscrite = db.Column(db.String(300))
    carte_membre_reed = db.Column(db.String(300))
    copie_cni = db.Column(db.String(300))
    
    # File paths for uploaded documents (bourse)
    certificat_scolarite = db.Column(db.String(300))
    bulletin_s2 = db.Column(db.String(300))  # Pour les élèves
    
    # Status: pending, approved, rejected
    status = db.Column(db.String(20), default='pending')
    
    # Timestamps
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)
    date_processed = db.Column(db.DateTime)
    
    # Admin notes
    admin_notes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<StudentRequest {self.nom} {self.prenom}>'

class ApplicationStatus(db.Model):
    __tablename__ = 'application_status'
    
    id = db.Column(db.Integer, primary_key=True)
    logement_open = db.Column(db.Boolean, default=False)
    bourse_open = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ApplicationStatus logement_open={self.logement_open}, bourse_open={self.bourse_open}>'
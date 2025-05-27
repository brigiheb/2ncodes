# -*- coding: utf-8 -*-
from .. import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    photo = db.Column(db.String(255), nullable=True)
    nom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    telephone = db.Column(db.String(20), nullable=False, unique=True)
    niveau = db.Column(db.Enum('niveau1', 'niveau2', 'niveau3'), nullable=False, default='niveau1')
    solde = db.Column(db.Float, nullable=False, default=0.0)
    etat = db.Column(db.Enum('actif', 'inactif'), nullable=False, default='actif')
    role = db.Column(db.Enum('manager', 'admin', 'revendeur'), nullable=False)  # Changed from type to role
    responsable = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Nullable for top-level users

    responsable_user = db.relationship('User', remote_side=[id], backref=db.backref('subordinates', lazy=True))

    def set_password(self, password):
        """Hash and store the password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify the password."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Convert the User object to a dictionary."""
        return {
            "id": self.id,
            "photo": self.photo,
            "nom": self.nom,
            "email": self.email,
            "telephone": self.telephone,
            "niveau": self.niveau,
            "solde": self.solde,
            "etat": self.etat,
            "role": self.role,  # Updated to role
            "responsable": self.responsable
        }

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

    # Include admin_boss in the role enum
    role = db.Column(db.Enum('manager', 'admin', 'revendeur', 'admin_boss'), nullable=False)

    # New: list of permissions granted by the manager to this admin_boss
    # Use JSON to store a list of strings (e.g., ["get_admins", "update_admin", ...])
    admin_boss_privilege = db.Column(db.JSON, nullable=True, default=[])

    responsable = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    responsable_user = db.relationship('User', remote_side=[id], backref=db.backref('subordinates', lazy=True))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "photo": self.photo,
            "nom": self.nom,
            "email": self.email,
            "telephone": self.telephone,
            "niveau": self.niveau,
            "solde": self.solde,
            "etat": self.etat,
            "role": self.role,
            "responsable": self.responsable,
            "admin_boss_privilege": self.admin_boss_privilege or []
        }

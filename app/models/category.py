# -*- coding: utf-8 -*-
from .. import db

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nom = db.Column(db.String(100), nullable=False, unique=True)  # Ensure this is UNIQUE
    photo = db.Column(db.String(255), nullable=True)
    etat = db.Column(db.Enum('actif', 'inactif'), nullable=False, default='actif')

    def to_dict(self):
        return {
            "id": self.id,
            "nom": self.nom,
            "photo": self.photo,
            "etat": self.etat
        }

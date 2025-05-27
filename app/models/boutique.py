# -*- coding: utf-8 -*-
from .. import db

class Boutique(db.Model):
    __tablename__ = 'boutiques'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    photo = db.Column(db.String(255), nullable=True)
    nom = db.Column(db.String(100), nullable=False, unique=True)

    def to_dict(self):
        """Convert the Boutique object to a dictionary."""
        return {
            "id": self.id,
            "photo": self.photo,
            "nom": self.nom
        }

# -*- coding: utf-8 -*-
from .. import db
from .boutique import Boutique

class Article(db.Model):
    __tablename__ = 'articles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    photo = db.Column(db.String(255), nullable=True)
    boutique_id = db.Column(db.Integer, db.ForeignKey('boutiques.id'), nullable=False)  # Foreign key to Boutique
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    prix_1 = db.Column(db.Float, nullable=False)
    prix_2 = db.Column(db.Float, nullable=True)
    prix_3 = db.Column(db.Float, nullable=True)
    etat = db.Column(db.Enum('actif', 'inactif'), nullable=False, default='actif')

    boutique = db.relationship('Boutique', backref=db.backref('articles', lazy=True))

    def to_dict(self):
        """Convert the Article object to a dictionary with boutique name."""
        return {
            "id": self.id,
            "photo": self.photo,
            "boutique": self.boutique.nom if self.boutique else None,
            "nom": self.nom,
            "description": self.description,
            "prix_1": self.prix_1,
            "prix_2": self.prix_2,
            "prix_3": self.prix_3,
            "etat": self.etat
        }

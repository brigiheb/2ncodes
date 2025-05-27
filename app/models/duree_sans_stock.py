# -*- coding: utf-8 -*-
from .. import db
from .product import Produit
from datetime import datetime

class DureeSansStock(db.Model):
    __tablename__ = 'duree_sans_stock'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    duree = db.Column(db.String(50), nullable=False)  # VARCHAR instead of ENUM
    prix_1 = db.Column(db.Float, nullable=False)
    prix_2 = db.Column(db.Float, nullable=False)
    prix_3 = db.Column(db.Float, nullable=False)
    fournisseur = db.Column(db.String(255), nullable=False)  # ✅ New column
    note = db.Column(db.Text, nullable=True)  # ✅ New note column
    date_ajout = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # ✅ New date column
    etat = db.Column(db.Enum('actif', 'inactif'), nullable=False, default='actif')

    produit = db.relationship('Produit', backref=db.backref('duree_sans_stock', lazy=True))

    def to_dict(self):
        """Convert the DureeSansStock object to a dictionary."""
        return {
            "id": self.id,
            "produit_name": self.produit.name if self.produit else None,
            "duree": self.duree,
            "prix_1": self.prix_1,
            "prix_2": self.prix_2,
            "prix_3": self.prix_3,
            "fournisseur": self.fournisseur,  # ✅
            "note": self.note,  # ✅
            "date_ajout": self.date_ajout.strftime('%Y-%m-%d %H:%M:%S'),  # ✅ formatted
            "etat": self.etat
        }

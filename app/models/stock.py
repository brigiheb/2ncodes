# -*- coding: utf-8 -*-
from .. import db
from datetime import datetime
from .product import Produit

class Stock(db.Model):
    __tablename__ = 'stock'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fournisseur = db.Column(db.String(100), nullable=False)
    prix_achat = db.Column(db.Float, nullable=False)  # Added prix_achat
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    duree = db.Column(db.Enum('1 jours', '14 jours', '1 mois', '6 mois', '12 mois', '15 mois'), nullable=False)
    code = db.Column(db.String(255), nullable=False, unique=True)
    note = db.Column(db.Text, nullable=True)  # Added note column
    date_ajout = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # ✅ Set default timestamp

    produit = db.relationship('Produit', backref=db.backref('stock', lazy=True))

    def to_dict(self):
        """Convert the Stock object to a dictionary."""
        return {
            "id": self.id,
            "produit_name": self.produit.name if self.produit else None,
            "fournisseur": self.fournisseur,
            "prix_achat": self.prix_achat,
            "duree": self.duree,
            "code": self.code,
            "note": self.note,
            "date_ajout": self.date_ajout.strftime('%Y-%m-%d %H:%M:%S')  # ✅ Format datetime
        }

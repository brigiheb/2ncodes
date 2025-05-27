# -*- coding: utf-8 -*-
from datetime import datetime
from .. import db
from .product import Produit
from .stock import Stock

class DureeAvecStock(db.Model):
    __tablename__ = 'duree_avec_stock'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    duree = db.Column(db.String(50), nullable=False)
    fournisseur = db.Column(db.String(255), nullable=False)
    prix_1 = db.Column(db.Float, nullable=False)
    prix_2 = db.Column(db.Float, nullable=False)
    prix_3 = db.Column(db.Float, nullable=False)
    quantite = db.Column(db.Integer, nullable=False, default=0)
    stock_minimale = db.Column(db.Integer, nullable=False)
    etat = db.Column(db.Enum('actif', 'inactif'), nullable=False, default='actif')
    note = db.Column(db.Text, nullable=True)  # ? New note column
    date_ajout = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # ? New date column

    produit = db.relationship('Produit', backref=db.backref('duree_avec_stock', lazy=True))

    def update_quantite(self):
        """Update the Quantit based on the Stock table."""
        self.quantite = db.session.query(db.func.count(Stock.id)).filter(
            Stock.produit_id == self.produit_id,
            Stock.duree == self.duree
        ).scalar() or 0

    def to_dict(self):
        """Convert DureeAvecStock object to dictionary and return the latest Quantit�."""
        return {
            "id": self.id,
            "produit_name": self.produit.name if self.produit else None,
            "duree": self.duree,
            "fournisseur": self.fournisseur,
            "prix_1": self.prix_1,
            "prix_2": self.prix_2,
            "prix_3": self.prix_3,
            "Quantite": self.quantite,
            "stock_minimale": self.stock_minimale,
            "etat": self.etat,
            "note": self.note,  # ? Included in dictionary
            "date_ajout": self.date_ajout.strftime('%Y-%m-%d %H:%M:%S')  # ? Convert to readable format
        }

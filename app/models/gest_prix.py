# -*- coding: utf-8 -*-
from .. import db
from datetime import datetime

class GestPrix(db.Model):
    __tablename__ = 'gest_prix'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Copied values from DureeAvecStock
    produit_name = db.Column(db.String(255), nullable=False)
    duree = db.Column(db.String(50), nullable=False)

    # Prices
    prix_achat = db.Column(db.Float, nullable=False)   # set from prix_1 / prix_2 / prix_3
    prix_vente = db.Column(db.Float, nullable=False)   # input manually by admin

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "produit_name": self.produit_name,
            "duree": self.duree,
            "prix_achat": self.prix_achat,
            "prix_vente": self.prix_vente,
        }

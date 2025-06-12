# -*- coding: utf-8 -*-
from .. import db
from datetime import datetime
from .user import User

class Historique(db.Model):
    __tablename__ = 'historiques'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('historiques', lazy=True))

    produit = db.Column(db.String(100), nullable=False)      # Name of the product bought
    duree = db.Column(db.String(50), nullable=False)         # Duration (e.g., 12 mois, 5 dt)
    codes = db.Column(db.Text, nullable=False)               # Could be single or multiple codes
    montant = db.Column(db.Float, nullable=False)            # How much it cost
    note = db.Column(db.String(255), nullable=True)          # Optional notes (e.g., source, customer, etc.)

    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_nom": self.user.nom if self.user else None,
            "produit": self.produit,
            "duree": self.duree,
            "codes": self.codes,
            "montant": self.montant,
            "note": self.note,
            "date": self.date.strftime('%Y-%m-%d %H:%M:%S')
        }

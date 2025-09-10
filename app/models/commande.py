# -*- coding: utf-8 -*-
from .. import db
from .product import Produit
from .duree_avec_stock import DureeAvecStock
from datetime import datetime

class Commande(db.Model):
    __tablename__ = 'commandes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    nom = db.Column(db.String(100), nullable=False)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    duree_id = db.Column(db.Integer, db.ForeignKey('duree_avec_stock.id'), nullable=False)
    login = db.Column(db.String(255), nullable=False)  # Email/Code/Login
    password_mac = db.Column(db.String(255), nullable=True)
    prix = db.Column(db.Float, nullable=False)
    note = db.Column(db.Text, nullable=True)
    etat = db.Column(db.Enum('en cours', 'en attente', 'annulé'), nullable=False, default='en attente')
    action = db.Column(db.Enum('accepter','annulé'), nullable=False, default='en attente')

    produit = db.relationship('Produit', backref=db.backref('commandes', lazy=True))
    duree = db.relationship('DureeAvecStock', backref=db.backref('commandes', lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.strftime("%Y-%m-%d %H:%M:%S"),
            "nom": self.nom,
            "produit": self.produit.name if self.produit else None,
            "duree": self.duree.duree if self.duree else None,
            "login": self.login,
            "password_mac": self.password_mac,
            "prix": self.prix,
            "note": self.note,
            "etat": self.etat
        }

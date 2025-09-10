# -*- coding: utf-8 -*-
from .. import db
from .category import Category
from .sous_category import SousCategory

class Produit(db.Model):
    __tablename__ = 'produits'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    photo = db.Column(db.String(255), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    sous_category_id = db.Column(db.Integer, db.ForeignKey('sous_categories.id'), nullable=True)
    etat = db.Column(db.Enum('actif', 'inactif'), nullable=False, default='actif')
    type = db.Column(db.Enum(
        'code', 'Netflix/Shahed', 'Smart App', 'Lien M3U', 
        'Panel Serveur', 'Add Package', 'Renew Package', 
        name='type_enum'
    ), nullable=False)
    affichage = db.Column(db.Integer, nullable=True)
    etat_commande = db.Column(db.Enum('instantané', 'sur commande'), nullable=False, default='instantané')
    add_status = db.Column(db.Enum('confirmé', 'annulé', 'en cours'), nullable=False, default='confirmé')

    category = db.relationship('Category', backref=db.backref('produits', lazy=True))
    sous_category = db.relationship('SousCategory', backref=db.backref('produits', lazy=True))

    def to_dict(self):
        """Convert the Produit object to a dictionary with category and sous-category names."""
        return {
            "id": self.id,
            "photo": self.photo,
            "name": self.name,
            "category_nom": self.category.nom if self.category else None,
            "sous_category_name": self.sous_category.name if self.sous_category else None,
            "etat": self.etat,
            "type": self.type,
            "affichage": self.affichage,
            "etat_commande": self.etat_commande,
            "add_status": self.add_status
        }
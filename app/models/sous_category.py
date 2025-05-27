# -*- coding: utf-8 -*-
from .. import db
from .category import Category

class SousCategory(db.Model):
    __tablename__ = 'sous_categories'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # Ensure this is UNIQUE
    photo = db.Column(db.String(255), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    etat = db.Column(db.Enum('actif', 'inactif'), nullable=False, default='actif')

    category = db.relationship('Category', backref=db.backref('sous_categories', lazy=True,cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "photo": self.photo,
            "category_name": self.category.nom if self.category else None,
            "etat": self.etat
        }

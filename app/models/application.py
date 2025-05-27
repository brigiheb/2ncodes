
# -*- coding: utf-8 -*-
from .. import db

class Application(db.Model):
    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    logo = db.Column(db.String(255), nullable=True)  # URL or path to the logo image
    nom = db.Column(db.String(100), nullable=False)  # Application name
    lien = db.Column(db.String(255), nullable=False)  # Application link (URL)

    def to_dict(self):
        """Convert the Application object to a dictionary."""
        return {
            "id": self.id,
            "logo": self.logo,
            "nom": self.nom,
            "lien": self.lien
        }

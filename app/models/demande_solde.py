# -*- coding: utf-8 -*-
from .. import db
from datetime import datetime

class DemandeSolde(db.Model):
    __tablename__ = 'demandes_solde'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    envoyee_par = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # User who sent the request
    montant = db.Column(db.Float, nullable=False)
    date_demande = db.Column(db.DateTime, default=datetime.utcnow)
    etat = db.Column(db.Enum('en cours', 'annulé', 'confirmé'), default='en cours', nullable=False)
    preuve = db.Column(db.String(255), nullable=True)  # Path to the proof image (optional)

    user = db.relationship('User', backref=db.backref('demandes_solde', lazy=True))

    def to_dict(self):
        """Convert the object to a JSON serializable dictionary."""
        return {
            "id": self.id,
            "envoyee_par": self.user.nom if self.user else None,  # Display user name instead of ID
            "montant": self.montant,
            "date_demande": self.date_demande.strftime('%Y-%m-%d %H:%M:%S'),
            "etat": self.etat,
            "preuve": self.preuve
        }

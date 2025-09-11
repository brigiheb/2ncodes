# app/models/commande_produit.py
# -*- coding: utf-8 -*-
from .. import db
from .user import User
from .product import Produit
from datetime import datetime

class CommandeEtat:
    EN_ATTENTE = "en_attente"
    ANNULE = "annule"
    ACCEPTE = "accepte"
    ENCOURS = "encours"
    CONFIRME = "confirme"

class CommandePaiement:
    IMPAYE = "impaye"
    PAYE = "paye"

class CommandeProduit(db.Model):
    __tablename__ = 'commandes_produit'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)

    # Relations
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False, index=True)

    # Duration (when applicable, e.g., from DureeSansStock). Kept optional.
    duree = db.Column(db.String(50), nullable=True)

    # Quantities & pricing (snapshot at order time)
    quantite = db.Column(db.Integer, nullable=False, default=1)
    prix_unitaire = db.Column(db.Float, nullable=False)   # resolved from applicable pricing rule
    montant = db.Column(db.Float, nullable=False)         # prix_unitaire * quantite

    # Client info
    nom = db.Column(db.String(100), nullable=False)       # Nom du client
    adresse = db.Column(db.String(255), nullable=False)   # Adresse livraison
    telephone = db.Column(db.String(20), nullable=False)  # Téléphone

    # Type-specific details (Smart App: mac, Panel Serveur: username/password,
    # Netflix/Shahed: email/password, Add/Renew Package: card_number, etc.)
    details = db.Column(db.JSON, nullable=True)

    date_creation = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    etat = db.Column(
        db.Enum(
            CommandeEtat.EN_ATTENTE,
            CommandeEtat.ANNULE,
            CommandeEtat.ACCEPTE,
            CommandeEtat.ENCOURS,
            CommandeEtat.CONFIRME,
            name="commande_produit_etat"
        ),
        default=CommandeEtat.EN_ATTENTE,
        nullable=False
    )

    paiement = db.Column(
        db.Enum(
            CommandePaiement.IMPAYE,
            CommandePaiement.PAYE,
            name="commande_produit_paiement"
        ),
        default=CommandePaiement.IMPAYE,
        nullable=False
    )

    # Relationships
    user = db.relationship('User', backref=db.backref('commandes_produit', lazy=True))
    produit = db.relationship('Produit', backref=db.backref('commandes_produit', lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "reference": self.reference,
            "user_id": self.user_id,
            "user_nom": self.user.nom if self.user else None,

            "produit_id": self.produit_id,
            "produit_name": self.produit.name if self.produit else None,

            "duree": self.duree,
            "quantite": self.quantite,
            "prix_unitaire": self.prix_unitaire,
            "montant": self.montant,

            "nom": self.nom,
            "adresse": self.adresse,
            "telephone": self.telephone,

            "details": self.details,  # mask sensitive fields in route responses if needed

            "date_creation": self.date_creation.strftime("%Y-%m-%d %H:%M:%S"),
            "etat": self.etat,
            "paiement": self.paiement,
        }

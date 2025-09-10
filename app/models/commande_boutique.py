# -*- coding: utf-8 -*-
from .. import db
from .user import User
from .article import Article
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

class CommandeBoutique(db.Model):
    __tablename__ = 'commandes_boutique'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)

    # Relations
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False)

    quantite = db.Column(db.Integer, nullable=False, default=1)
    montant = db.Column(db.Float, nullable=False)

    nom = db.Column(db.String(100), nullable=False)       # Nom du client
    adresse = db.Column(db.String(255), nullable=False)   # Adresse livraison
    telephone = db.Column(db.String(20), nullable=False)  # Téléphone

    date_creation = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    etat = db.Column(
        db.Enum(
            CommandeEtat.EN_ATTENTE,
            CommandeEtat.ANNULE,
            CommandeEtat.ACCEPTE,
            CommandeEtat.ENCOURS,
            CommandeEtat.CONFIRME,
            name="commande_etat"
        ),
        default=CommandeEtat.EN_ATTENTE,
        nullable=False
    )

    paiement = db.Column(
        db.Enum(
            CommandePaiement.IMPAYE,
            CommandePaiement.PAYE,
            name="commande_paiement"
        ),
        default=CommandePaiement.IMPAYE,
        nullable=False
    )

    # Relationships
    user = db.relationship('User', backref=db.backref('commandes', lazy=True))
    article = db.relationship('Article', backref=db.backref('commandes', lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "reference": self.reference,
            "user_id": self.user_id,
            "user_nom": self.user.nom if self.user else None,
            "article_id": self.article_id,
            "article_nom": self.article.nom if self.article else None,
            "quantite": self.quantite,
            "montant": self.montant,
            "nom": self.nom,
            "adresse": self.adresse,
            "telephone": self.telephone,
            "date_creation": self.date_creation.strftime("%Y-%m-%d %H:%M:%S"),
            "etat": self.etat,
            "paiement": self.paiement,
        }

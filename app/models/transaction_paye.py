# -*- coding: utf-8 -*-
from .. import db
from datetime import datetime

class TransactionPaye(db.Model):
    __tablename__ = 'transaction_paye'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    envoyee_par = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recue_par = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    preuve = db.Column(db.String(255), nullable=True)  # Optional image path
    date_transaction = db.Column(db.DateTime, default=datetime.utcnow)
    date_paiement = db.Column(db.DateTime, default=datetime.utcnow)
    etat = db.Column(db.Enum('paye', name='etat_paye'), default='paye', nullable=False)

    sender = db.relationship('User', foreign_keys=[envoyee_par], backref=db.backref('transactions_envoyees', lazy=True))
    receiver = db.relationship('User', foreign_keys=[recue_par], backref=db.backref('transactions_recues', lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "envoyee_par": self.sender.nom if self.sender else None,
            "recue_par": self.receiver.nom if self.receiver else None,
            "montant": self.montant,
            "preuve": self.preuve,
            "date_transaction": self.date_transaction.strftime('%Y-%m-%d %H:%M:%S'),
            "date_paiement": self.date_paiement.strftime('%Y-%m-%d %H:%M:%S'),
            "etat": self.etat
        }

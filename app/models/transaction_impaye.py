# -*- coding: utf-8 -*-
from .. import db
from datetime import datetime

class TransactionImpaye(db.Model):
    __tablename__ = 'transaction_impaye'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    envoyee_par = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recue_par = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    date_transaction = db.Column(db.DateTime, default=datetime.utcnow)
    etat = db.Column(db.Enum('impaye', name='etat_impaye'), default='impaye', nullable=False)

    sender = db.relationship('User', foreign_keys=[envoyee_par], backref=db.backref('transactions_impaye_envoyees', lazy=True))
    receiver = db.relationship('User', foreign_keys=[recue_par], backref=db.backref('transactions_impaye_recues', lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "envoyee_par": self.sender.nom if self.sender else None,
            "recue_par": self.receiver.nom if self.receiver else None,
            "montant": self.montant,
            "date_transaction": self.date_transaction.strftime('%Y-%m-%d %H:%M:%S'),
            "etat": self.etat
        }

# -*- coding: utf-8 -*-
from .. import db
from datetime import datetime

class ReturnRequest(db.Model):
    __tablename__ = "return_requests"
    id = db.Column(db.Integer, primary_key=True)
    historique_id = db.Column(db.Integer, db.ForeignKey("historiques.id"), nullable=False)
    requester_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reason        = db.Column(db.Text, nullable=False)
    status        = db.Column(db.String(20), default="pending", nullable=False)  # pending|approved|rejected
    reviewed_by   = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at   = db.Column(db.DateTime)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

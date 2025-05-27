# -*- coding: utf-8 -*-
from .. import db
from datetime import datetime
import enum
from sqlalchemy import Enum


class ItemType(enum.Enum):
    product = "product"
    category = "category"
    sous_category = "sous_category"
    boutique = "boutique"
    article = "article"
    application = "application"


class VisibleItem(db.Model):
    __tablename__ = 'visible_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    item_type = db.Column(Enum(ItemType), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "item_id": self.item_id,
            "item_type": self.item_type.value,
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

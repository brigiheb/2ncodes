# -*- coding: utf-8 -*-
from .. import db
from .user import User
from .article import Article

class Panier(db.Model):
    __tablename__ = 'paniers'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'article_id', name='uq_panier_user_article'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False, index=True)
    quantite = db.Column(db.Integer, nullable=False, default=1)

    # Relationships
    user = db.relationship('User', backref=db.backref('paniers', lazy=True, cascade="all, delete-orphan"))
    article = db.relationship('Article', backref=db.backref('paniers', lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_nom": self.user.nom if self.user else None,
            "article_id": self.article_id,
            "article_nom": self.article.nom if self.article else None,
            "quantite": self.quantite
        }

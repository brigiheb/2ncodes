from .. import db
from sqlalchemy.dialects.mysql import LONGTEXT


class GestMessage(db.Model):
    __tablename__ = 'gest_message'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    text = db.Column(LONGTEXT, nullable=True)

    img_path = db.Column(db.String(255), nullable=True)
    video_path = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(255), nullable=True)
    to = db.Column(db.Enum('admin', 'revendeur', 'all'), nullable=False)
    etat = db.Column(db.Enum('afficher', 'masquer'), nullable=False, default='afficher')

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "img_path": f"/{self.img_path}" if self.img_path else None,
            "video_path": f"/{self.video_path}" if self.video_path else None,
            "file_path": f"/{self.file_path}" if self.file_path else None,
            "to": self.to,
            "etat": self.etat
        }

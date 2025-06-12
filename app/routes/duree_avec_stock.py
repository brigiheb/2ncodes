# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from .. import db
from ..models.duree_avec_stock import DureeAvecStock
from ..models.stock import Stock
from ..models.product import Produit

duree_avec_stock_bp = Blueprint('duree_avec_stock', __name__)

# ===================== Helper ===================== #
def get_stock_quantity(produit_id, duree):
    """Count stock entries matching produit and duree."""
    return Stock.query.filter_by(produit_id=produit_id, duree=duree).count()

# ===================== ADD DUREE AVEC STOCK ===================== #
@duree_avec_stock_bp.route('/add', methods=['POST'])
def add_duree_avec_stock():
    """Add a new entry to duree_avec_stock."""
    data = request.get_json()
    produit_id = data.get('produit_id')
    duree = data.get('duree')
    fournisseur = data.get('fournisseur')
    prix_1 = data.get('prix_1')
    prix_2 = data.get('prix_2')
    prix_3 = data.get('prix_3')
    stock_minimale = data.get('stock_minimale')
    etat = data.get('etat', 'actif')
    note = data.get('note', None)

    produit = Produit.query.get(produit_id)
    if not produit:
        return jsonify({"error": f"Produit with ID {produit_id} not found"}), 404

    new_entry = DureeAvecStock(
        produit_id=produit_id,
        duree=duree,
        fournisseur=fournisseur,
        prix_1=prix_1,
        prix_2=prix_2,
        prix_3=prix_3,
        stock_minimale=stock_minimale,
        etat=etat,
        note=note
    )

    new_entry.update_quantite()
    new_entry.update_moyenne()

    db.session.add(new_entry)
    db.session.commit()

    return jsonify(new_entry.to_dict()), 201

# ===================== GET ALL ===================== #
@duree_avec_stock_bp.route('/get_all', methods=['GET'])
def get_all_duree_avec_stock():
    records = DureeAvecStock.query.all()
    return jsonify([record.to_dict() for record in records]), 200

# ===================== GET BY ID ===================== #
@duree_avec_stock_bp.route('/get/<int:record_id>', methods=['GET'])
def get_duree_avec_stock(record_id):
    record = DureeAvecStock.query.get(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(record.to_dict()), 200

# ===================== UPDATE ===================== #
@duree_avec_stock_bp.route('/update/<int:record_id>', methods=['PUT'])
def update_duree_avec_stock(record_id):
    record = DureeAvecStock.query.get(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    data = request.get_json()

    record.duree = data.get('duree', record.duree)
    record.fournisseur = data.get('fournisseur', record.fournisseur)
    record.prix_1 = data.get('prix_1', record.prix_1)
    record.prix_2 = data.get('prix_2', record.prix_2)
    record.prix_3 = data.get('prix_3', record.prix_3)
    record.stock_minimale = data.get('stock_minimale', record.stock_minimale)
    record.etat = data.get('etat', record.etat)
    record.note = data.get('note', record.note)

    record.quantite = get_stock_quantity(record.produit_id, record.duree)
    record.update_moyenne()

    db.session.commit()
    return jsonify(record.to_dict()), 200

# ===================== DELETE ===================== #
@duree_avec_stock_bp.route('/delete/<int:record_id>', methods=['DELETE'])
def delete_duree_avec_stock(record_id):
    record = DureeAvecStock.query.get(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404

    db.session.delete(record)
    db.session.commit()
    return jsonify({"message": "Record deleted successfully"}), 200

# ===================== RECALCULATE MOYENNE FOR ALL ===================== #
@duree_avec_stock_bp.route('/recalculate_moyenne_all', methods=['POST'])
def recalculate_all_moyenne():
    """Recalculate moyenne and quantite for all existing records."""
    records = DureeAvecStock.query.all()
    for record in records:
        record.update_quantite()
        record.update_moyenne()
    db.session.commit()
    return jsonify({"message": "Moyenne and quantite recalculated for all entries"}), 200

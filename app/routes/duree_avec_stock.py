# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from .. import db
from ..models.duree_avec_stock import DureeAvecStock
from ..models.stock import Stock
from ..models.product import Produit
from sqlalchemy import func
from sqlalchemy import func, cast, String, or_

duree_avec_stock_bp = Blueprint('duree_avec_stock', __name__)

# ===================== Helper ===================== #
def update_quantite_moyenne_if_exists(produit_id, duree):
    """Update quantite and moyenne for existing DureeAvecStock record if it exists (case-insensitive)."""
    normalized_duree = duree.strip().lower()

    record = DureeAvecStock.query.filter(
        DureeAvecStock.produit_id == produit_id,
        func.lower(func.trim(DureeAvecStock.duree)) == normalized_duree
    ).first()

    if record:
        record.update_quantite()
        record.update_moyenne()
        db.session.commit()

# ===================== ADD DUREE AVEC STOCK ===================== #
@duree_avec_stock_bp.route('/add', methods=['POST'])
def add_duree_avec_stock():
    data = request.get_json()
    produit_id = data.get('produit_id')
    duree = data.get('duree', '').strip().lower()
    prix_1 = data.get('prix_1')
    prix_2 = data.get('prix_2')
    prix_3 = data.get('prix_3')
    stock_minimale = data.get('stock_minimale')
    etat = data.get('etat', 'actif')
    note = data.get('note', None)

    # Validate required fields
    if not all([produit_id, duree, prix_1 is not None, prix_2 is not None, prix_3 is not None, stock_minimale is not None]):
        return jsonify({"error": "Missing required fields"}), 400

    # Check for existing record
    existing_record = DureeAvecStock.query.filter(
        DureeAvecStock.produit_id == produit_id,
        func.lower(func.trim(DureeAvecStock.duree)) == duree
    ).first()
    if existing_record:
        return jsonify({"error": f"A duration with produit_id {produit_id} and duree '{duree}' already exists"}), 409

    produit = Produit.query.get(produit_id)
    if not produit:
        return jsonify({"error": f"Produit with ID {produit_id} not found"}), 404

    new_entry = DureeAvecStock(
        produit_id=produit_id,
        duree=duree,
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

    # Update related records
    update_quantite_moyenne_if_exists(produit_id, duree)

    return jsonify(new_entry.to_dict()), 201

# ===================== GET ALL ===================== #
@duree_avec_stock_bp.route('/get_all', methods=['GET'])
def get_all_duree_avec_stock():
    try:
        # Get query parameters
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        search_query = request.args.get('search', type=str, default="").strip().lower()
        produit_id = request.args.get('produit_id', type=int, default=None)
        duree = request.args.get('duree', type=str, default="").strip().lower()
        etat = request.args.get('etat', type=str, default="").strip().lower()

        # Start with base query, joining Produit for produit_name
        query = DureeAvecStock.query.join(Produit, DureeAvecStock.produit_id == Produit.id)

        # Apply search across all fields
        if search_query:
            query = query.filter(
                or_(
                    Produit.name.ilike(f"%{search_query}%"),
                    DureeAvecStock.duree.ilike(f"%{search_query}%"),
                    cast(DureeAvecStock.prix_1, String).ilike(f"%{search_query}%"),
                    cast(DureeAvecStock.prix_2, String).ilike(f"%{search_query}%"),
                    cast(DureeAvecStock.prix_3, String).ilike(f"%{search_query}%"),
                    cast(DureeAvecStock.moyenne, String).ilike(f"%{search_query}%"),
                    cast(DureeAvecStock.quantite, String).ilike(f"%{search_query}%"),
                    cast(DureeAvecStock.stock_minimale, String).ilike(f"%{search_query}%"),
                    cast(DureeAvecStock.note, String).ilike(f"%{search_query}%"),
                    DureeAvecStock.etat.ilike(f"%{search_query}%"),
                    cast(DureeAvecStock.date_ajout, String).ilike(f"%{search_query}%")
                )
            )

        # Apply filters
        if produit_id is not None:
            query = query.filter(DureeAvecStock.produit_id == produit_id)
        if duree:
            query = query.filter(func.lower(func.trim(DureeAvecStock.duree)) == duree)
        if etat:
            query = query.filter(DureeAvecStock.etat.ilike(etat))

        # Paginate and order results
        paginated = query.order_by(DureeAvecStock.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
        results = paginated.items

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "records": [record.to_dict() for record in results]
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to fetch durations: {str(e)}"}), 500

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

    payload = request.get_json()
    data = payload.get("data") if "data" in payload else payload

    record.produit_id = data.get('produit_id', record.produit_id)
    record.duree = data.get('duree', record.duree).strip().lower()
    record.prix_1 = data.get('prix_1', record.prix_1)
    record.prix_2 = data.get('prix_2', record.prix_2)
    record.prix_3 = data.get('prix_3', record.prix_3)
    record.stock_minimale = data.get('stock_minimale', record.stock_minimale)
    record.etat = data.get('etat', record.etat)
    record.note = data.get('note', record.note)

    if not all([
        record.produit_id,
        record.duree,
        record.prix_1 is not None,
        record.prix_2 is not None,
        record.prix_3 is not None,
        record.stock_minimale is not None
    ]):
        return jsonify({"error": "Missing required fields after update"}), 400

    existing_record = DureeAvecStock.query.filter(
        DureeAvecStock.produit_id == record.produit_id,
        func.lower(func.trim(DureeAvecStock.duree)) == record.duree,
        DureeAvecStock.id != record_id
    ).first()
    if existing_record:
        return jsonify({"error": f"A duration with produit_id {record.produit_id} and duree '{record.duree}' already exists"}), 409

    produit = Produit.query.get(record.produit_id)
    if not produit:
        return jsonify({"error": f"Produit with ID {record.produit_id} not found"}), 404

    record.update_quantite()
    record.update_moyenne()

    db.session.commit()

    update_quantite_moyenne_if_exists(record.produit_id, record.duree)

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
    records = DureeAvecStock.query.all()
    for record in records:
        record.update_quantite()
        record.update_moyenne()
    db.session.commit()
    return jsonify({"message": "Moyenne and quantite recalculated for all entries"}), 200

# ===================== GET FILTER OPTIONS ===================== #
@duree_avec_stock_bp.route('/get_filter_options', methods=['GET'])
def get_filter_options():
    try:
        # Fetch unique produit names with IDs
        produits = (
            db.session.query(Produit.id, Produit.name.label('produit_name'))
            .join(DureeAvecStock, DureeAvecStock.produit_id == Produit.id)
            .distinct()
            .order_by(Produit.name.asc())
            .all()
        )

        # Fetch unique duree values
        durees = (
            db.session.query(func.lower(func.trim(DureeAvecStock.duree)).label('duree'))
            .distinct()
            .order_by(func.lower(func.trim(DureeAvecStock.duree)).asc())
            .all()
        )

        # Format response
        response = {
            "produits": [{"id": p.id, "produit_name": p.produit_name} for p in produits],
            "durees": [d.duree for d in durees]
        }

        return jsonify(response), 200
    except Exception as e:
        return jsonify({"error": f"Failed to fetch filter options: {str(e)}"}), 500
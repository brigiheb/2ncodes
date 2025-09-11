# routes/gest_prix.py
# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from .. import db
from ..models.user import User
from ..models.gest_prix import GestPrix
from ..models.duree_avec_stock import DureeAvecStock
from ..models.duree_sans_stock import DureeSansStock
from ..models.product import Produit

gest_prix_bp = Blueprint('gest_prix', __name__)

# ----------------- Helpers -----------------

def require_admin(user: User):
    return bool(user and user.role == 'admin')

def prix_achat_for_niveau(row_with_prices, niveau: str) -> float:
    """
    row_with_prices can be DureeAvecStock or DureeSansStock (must have prix_1, prix_2, prix_3).
    """
    n = (niveau or 'niveau1').lower()
    if n == 'niveau2':
        return float(row_with_prices.prix_2)
    if n == 'niveau3':
        return float(row_with_prices.prix_3)
    return float(row_with_prices.prix_1)

def normalize_duree(s: str) -> str:
    return (s or "").strip().lower()

def _find_in_avec_stock_by_name_and_duree(produit_name: str, duree: str):
    pn = (produit_name or "").strip()
    d = normalize_duree(duree)
    return (
        db.session.query(DureeAvecStock)
        .join(Produit, DureeAvecStock.produit_id == Produit.id)
        .filter(
            func.lower(func.trim(Produit.name)) == func.lower(func.trim(pn)),
            func.lower(func.trim(DureeAvecStock.duree)) == d
        )
        .first()
    )

def _find_in_sans_stock_by_name_and_duree(produit_name: str, duree: str):
    pn = (produit_name or "").strip()
    d = normalize_duree(duree)
    return (
        db.session.query(DureeSansStock)
        .join(Produit, DureeSansStock.produit_id == Produit.id)
        .filter(
            func.lower(func.trim(Produit.name)) == func.lower(func.trim(pn)),
            func.lower(func.trim(DureeSansStock.duree)) == d
        )
        .first()
    )

def find_any_by_name_and_duree(produit_name: str, duree: str):
    """
    Try to find a matching (produit, duree) in DureeAvecStock first, then DureeSansStock.
    Returns a tuple (model_name, row) where model_name in {"avec", "sans"} or (None, None).
    """
    row = _find_in_avec_stock_by_name_and_duree(produit_name, duree)
    if row:
        return "avec", row
    row = _find_in_sans_stock_by_name_and_duree(produit_name, duree)
    if row:
        return "sans", row
    return None, None

def _collect_rows(etat_filter: str, search: str):
    """
    Collect (produit_name, duree, source, row_obj) from both tables, applying etat and search.
    source: "avec" or "sans"
    """
    # Base queries
    q_avec = db.session.query(DureeAvecStock, Produit.name).join(
        Produit, DureeAvecStock.produit_id == Produit.id
    )
    q_sans = db.session.query(DureeSansStock, Produit.name).join(
        Produit, DureeSansStock.produit_id == Produit.id
    )

    if etat_filter:
        q_avec = q_avec.filter(DureeAvecStock.etat == etat_filter)
        q_sans = q_sans.filter(DureeSansStock.etat == etat_filter)

    if search:
        like = f"%{search}%"
        q_avec = q_avec.filter(
            db.or_(
                func.lower(Produit.name).like(like),
                func.lower(DureeAvecStock.duree).like(like),
            )
        )
        q_sans = q_sans.filter(
            db.or_(
                func.lower(Produit.name).like(like),
                func.lower(DureeSansStock.duree).like(like),
            )
        )

    # Order newest first by id (independently) then merge
    q_avec = q_avec.order_by(DureeAvecStock.id.desc())
    q_sans = q_sans.order_by(DureeSansStock.id.desc())

    rows = []
    for das, pname in q_avec.all():
        rows.append((pname, das.duree, "avec", das))
    for dss, pname in q_sans.all():
        rows.append((pname, dss.duree, "sans", dss))

    # Final combined order: just keep as appended (already desc inside each)
    return rows

# ----------------- Endpoints -----------------

@gest_prix_bp.route('/preview', methods=['GET'])
@jwt_required()
def preview_all_from_das():
    """
    ADMIN-ONLY
    Preview all rows from DureeAvecStock + DureeSansStock with:
      - produit_name
      - duree
      - prix_achat (computed from admin.niveau)
      - prix_vente (from GestPrix snapshot if exists, else None)
    Query params:
      - search: str (optional)
      - etat: 'actif' | 'inactif' (default 'actif')
      - page: int (default 1)
      - per_page: int (default 20)
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not require_admin(user):
        return jsonify({"error": "Access denied. Admin only."}), 403

    search = (request.args.get('search') or "").strip().lower()
    etat = (request.args.get('etat') or "actif").strip().lower()
    page = request.args.get('page', type=int, default=1)
    per_page = request.args.get('per_page', type=int, default=20)

    rows = _collect_rows(etat_filter=etat, search=search)

    # Map existing GestPrix by (produit_name_lower, duree_lower)
    gp_rows = GestPrix.query.all()
    gp_map = {(gp.produit_name.strip().lower(), normalize_duree(gp.duree)): gp for gp in gp_rows}

    items = []
    for produit_name, duree, _source, row in rows:
        key = (produit_name.strip().lower() if produit_name else "", normalize_duree(duree))
        prix_achat = prix_achat_for_niveau(row, user.niveau)
        prix_vente = gp_map.get(key).prix_vente if key in gp_map else None
        items.append({
            "produit_name": produit_name,
            "duree": duree,
            "prix_achat": prix_achat,
            "prix_vente": prix_vente
        })

    # Manual pagination over merged list
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    paged_items = items[start:end]

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": (total + per_page - 1) // per_page if total else 1,
        "records": paged_items
    }), 200


@gest_prix_bp.route('/set_price', methods=['POST'])
@jwt_required()
def set_price():
    """
    ADMIN-ONLY
    Upsert one GestPrix row (global snapshot) for (produit_name, duree).
    Body JSON:
      - produit_name: string (required)
      - duree: string (required)
      - prix_vente: float (required)
    Behavior:
      - Finds matching row by produit_name + duree in DureeAvecStock OR DureeSansStock.
      - Computes prix_achat based on admin.niveau.
      - Creates/updates GestPrix snapshot with prix_achat and prix_vente.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not require_admin(user):
        return jsonify({"error": "Access denied. Admin only."}), 403

    data = request.get_json() or {}
    produit_name = (data.get("produit_name") or "").strip()
    duree = (data.get("duree") or "").strip()
    prix_vente = data.get("prix_vente")

    if not produit_name or not duree or prix_vente is None:
        return jsonify({"error": "produit_name, duree and prix_vente are required."}), 400

    source, row = find_any_by_name_and_duree(produit_name, duree)
    if not row:
        return jsonify({"error": "No matching (produit, duree) found in stock tables."}), 404

    prix_achat = prix_achat_for_niveau(row, user.niveau)

    key = (produit_name.strip().lower(), normalize_duree(duree))
    gp = (
        GestPrix.query
        .filter(func.lower(func.trim(GestPrix.produit_name)) == key[0],
                func.lower(func.trim(GestPrix.duree)) == key[1])
        .first()
    )

    if gp:
        gp.prix_achat = prix_achat
        gp.prix_vente = float(prix_vente)
    else:
        gp = GestPrix(
            produit_name=produit_name,
            duree=duree,
            prix_achat=prix_achat,
            prix_vente=float(prix_vente)
        )
        db.session.add(gp)

    db.session.commit()

    return jsonify({
        "message": "Prix de vente enregistré.",
        "row": gp.to_dict()
    }), 200


@gest_prix_bp.route('/sync_all', methods=['POST'])
@jwt_required()
def sync_all():
    """
    ADMIN-ONLY
    Ensure GestPrix has one row for every (produit, duree) in BOTH:
      - DureeAvecStock (etat = 'actif')
      - DureeSansStock (etat = 'actif')
    Since prix_vente is NOT NULL, we need a default. You can pass:
      - default_margin: float (optional, default=5), used as prix_vente = prix_achat + default_margin
    Existing rows are left untouched except prix_achat will be refreshed for the current admin's niveau.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not require_admin(user):
        return jsonify({"error": "Access denied. Admin only."}), 403

    payload = request.get_json() or {}
    default_margin = float(payload.get("default_margin", 5))

    # Load all active rows from both tables with product names
    avec_list = (
        db.session.query(DureeAvecStock, Produit.name)
        .join(Produit, DureeAvecStock.produit_id == Produit.id)
        .filter(DureeAvecStock.etat == 'actif')
        .all()
    )
    sans_list = (
        db.session.query(DureeSansStock, Produit.name)
        .join(Produit, DureeSansStock.produit_id == Produit.id)
        .filter(DureeSansStock.etat == 'actif')
        .all()
    )

    # Build map of existing GP rows
    gp_rows = GestPrix.query.all()
    gp_map = {(gp.produit_name.strip().lower(), normalize_duree(gp.duree)): gp for gp in gp_rows}

    created, updated = 0, 0

    # Upsert for DureeAvecStock
    for row, pname in avec_list:
        if not pname:
            continue
        key = (pname.strip().lower(), normalize_duree(row.duree))
        prix_achat = prix_achat_for_niveau(row, user.niveau)
        if key in gp_map:
            gp = gp_map[key]
            if gp.prix_achat != prix_achat:
                gp.prix_achat = prix_achat
                updated += 1
        else:
            gp = GestPrix(
                produit_name=pname,
                duree=row.duree,
                prix_achat=prix_achat,
                prix_vente=prix_achat + default_margin
            )
            db.session.add(gp)
            created += 1

    # Upsert for DureeSansStock
    for row, pname in sans_list:
        if not pname:
            continue
        key = (pname.strip().lower(), normalize_duree(row.duree))
        prix_achat = prix_achat_for_niveau(row, user.niveau)
        if key in gp_map:
            gp = gp_map[key]
            if gp.prix_achat != prix_achat:
                gp.prix_achat = prix_achat
                updated += 1
        else:
            gp = GestPrix(
                produit_name=pname,
                duree=row.duree,
                prix_achat=prix_achat,
                prix_vente=prix_achat + default_margin
            )
            db.session.add(gp)
            created += 1

    db.session.commit()
    return jsonify({"message": "Sync completed", "created": created, "updated": updated}), 200


@gest_prix_bp.route('/delete/<int:row_id>', methods=['DELETE'])
@jwt_required()
def delete_row(row_id):
    """
    ADMIN-ONLY
    Delete one GestPrix row.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not require_admin(user):
        return jsonify({"error": "Access denied. Admin only."}), 403

    row = GestPrix.query.get(row_id)
    if not row:
        return jsonify({"error": "Row not found"}), 404

    db.session.delete(row)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200

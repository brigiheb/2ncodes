# routes/gest_prix.py
# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from .. import db
from ..models.user import User
from ..models.gest_prix import GestPrix
from ..models.duree_avec_stock import DureeAvecStock
from ..models.product import Produit

gest_prix_bp = Blueprint('gest_prix', __name__)

# ----------------- Helpers -----------------

def require_admin(user: User):
    return bool(user and user.role == 'admin')

def prix_achat_for_niveau(das: DureeAvecStock, niveau: str) -> float:
    n = (niveau or 'niveau1').lower()
    if n == 'niveau2':
        return float(das.prix_2)
    if n == 'niveau3':
        return float(das.prix_3)
    return float(das.prix_1)

def normalize_duree(s: str) -> str:
    return (s or "").strip().lower()

# Find one DureeAvecStock by produit_name + duree (case-insensitive on both sides)
def find_das_by_name_and_duree(produit_name: str, duree: str):
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

# ----------------- Endpoints -----------------

@gest_prix_bp.route('/preview', methods=['GET'])
@jwt_required()
def preview_all_from_das():
    """
    ADMIN-ONLY
    Preview all rows from DureeAvecStock with:
      - produit_name (from Produit)
      - duree
      - prix_achat (computed from admin.niveau)
      - prix_vente (from GestPrix snapshot if exists, else None)
    Query params:
      - search: search produit_name or duree (optional)
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

    q = DureeAvecStock.query.join(Produit, DureeAvecStock.produit_id == Produit.id)

    if etat:
        q = q.filter(DureeAvecStock.etat == etat)

    if search:
        q = q.filter(
            db.or_(
                func.lower(Produit.name).like(f"%{search}%"),
                func.lower(DureeAvecStock.duree).like(f"%{search}%"),
            )
        )

    q = q.order_by(DureeAvecStock.id.desc())
    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    das_rows = paginated.items

    # Map existing GestPrix by (produit_name_lower, duree_lower)
    gp_rows = GestPrix.query.all()
    gp_map = {(gp.produit_name.strip().lower(), normalize_duree(gp.duree)): gp for gp in gp_rows}

    items = []
    for das in das_rows:
        produit_name = das.produit.name if das.produit else None
        duree = das.duree
        key = (produit_name.strip().lower() if produit_name else "", normalize_duree(duree))
        prix_achat = prix_achat_for_niveau(das, user.niveau)
        prix_vente = gp_map.get(key).prix_vente if key in gp_map else None

        items.append({
            "produit_name": produit_name,
            "duree": duree,
            "prix_achat": prix_achat,
            "prix_vente": prix_vente
        })

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": paginated.total,
        "pages": paginated.pages,
        "records": items
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
      - Finds matching DureeAvecStock row by produit_name + duree.
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

    das = find_das_by_name_and_duree(produit_name, duree)
    if not das:
        return jsonify({"error": "No matching (produit, duree) found in duree_avec_stock."}), 404

    prix_achat = prix_achat_for_niveau(das, user.niveau)

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
    Ensure GestPrix has one row for every (produit, duree) in DureeAvecStock.
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

    # Load all DAS (typically only 'actif'; change filter if needed)
    das_list = (
        db.session.query(DureeAvecStock)
        .join(Produit, DureeAvecStock.produit_id == Produit.id)
        .filter(DureeAvecStock.etat == 'actif')
        .all()
    )

    # Build map of existing GP rows
    gp_rows = GestPrix.query.all()
    gp_map = {(gp.produit_name.strip().lower(), normalize_duree(gp.duree)): gp for gp in gp_rows}

    created, updated = 0, 0

    for das in das_list:
        produit_name = das.produit.name if das.produit else None
        if not produit_name:
            continue
        duree = das.duree
        key = (produit_name.strip().lower(), normalize_duree(duree))
        prix_achat = prix_achat_for_niveau(das, user.niveau)

        if key in gp_map:
            # refresh prix_achat snapshot; keep prix_vente as-is
            gp = gp_map[key]
            if gp.prix_achat != prix_achat:
                gp.prix_achat = prix_achat
                updated += 1
        else:
            # create with default prix_vente (required non-null)
            gp = GestPrix(
                produit_name=produit_name,
                duree=duree,
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

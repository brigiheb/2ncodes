# app/routes/commande_produit.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from sqlalchemy import or_, func, cast, String
from .. import db
from ..models.commande_produit import (
    CommandeProduit,
    CommandeEtat,
    CommandePaiement
)
from ..models.product import Produit
from ..models.user import User
from ..models.duree_sans_stock import DureeSansStock
import uuid

commande_produit_bp = Blueprint('commande_produit', __name__, url_prefix='/commande_produit')


# -----------------------
# Helpers
# -----------------------
def generate_reference():
    """Generate a unique order reference."""
    return f"CMDP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

def _required_type_fields(prod_type: str):
    """
    Return a tuple: (required_keys, extractor)
    - required_keys: list of required keys in payload for given product type
    - extractor: function(data) -> dict to be stored in details
    """
    t = (prod_type or "").strip().lower()

    if t == "smart app":
        # requires MAC address
        def ex(d):
            return {"mac": (d.get("mac") or d.get("adresse_mac") or "").strip()}
        return (["mac"], ex)

    if t == "panel serveur":
        # requires username and password
        def ex(d):
            return {
                "username": (d.get("username") or "").strip(),
                "password": (d.get("password") or "").strip(),
            }
        return (["username", "password"], ex)

    if t in ("netflix", "shahed"):
        # requires email and password
        def ex(d):
            return {
                "email": (d.get("email") or "").strip(),
                "password": (d.get("password") or "").strip(),
            }
        return (["email", "password"], ex)

    if t in ("add pachage", "add package", "renew package", "add package or renew package"):
        # requires card_number
        def ex(d):
            return {"card_number": (d.get("card_number") or "").strip()}
        return (["card_number"], ex)

    # default: no extra fields
    return ([], lambda d: {})

def _prix_unitaire_for_user(dss: DureeSansStock, user: User) -> float:
    """Resolve unit price from DureeSansStock according to user's niveau."""
    niveau = (user.niveau or "niveau1").lower()
    if niveau == "niveau2":
        return float(dss.prix_2)
    if niveau == "niveau3":
        return float(dss.prix_3)
    return float(dss.prix_1)

def _is_manager_or_boss(u: User) -> bool:
    return bool(u and u.role in ["manager", "admin_boss"])


# ================================
# USER SIDE
# ================================
@commande_produit_bp.route('/checkout', methods=['POST'])
@jwt_required()
def checkout():
    """
    Create a new CommandeProduit from a product and DureeSansStock duration.

    Expected JSON/form:
      - produit_id (int)        : required
      - duree (str)             : required (must exist in DureeSansStock for produit)
      - quantite (int)          : default 1
      - nom (str), adresse (str), telephone (str)   : required
      - type-specific fields:
          * Smart App           -> mac
          * Panel Serveur       -> username, password
          * Netflix / Shahed    -> email, password
          * Add Package/Renew   -> card_number
    """
    user_id = get_jwt_identity()
    current_user = User.query.get(user_id)
    if not current_user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or request.form

    produit_id = data.get("produit_id")
    duree = (data.get("duree") or "").strip()
    quantite = int(data.get("quantite", 1))
    nom = (data.get("nom") or "").strip()
    adresse = (data.get("adresse") or "").strip()
    telephone = (data.get("telephone") or "").strip()

    if not produit_id or not duree or not nom or not adresse or not telephone:
        return jsonify({"error": "produit_id, duree, nom, adresse, telephone are required"}), 400
    if quantite <= 0:
        return jsonify({"error": "quantite must be a positive integer"}), 400

    produit = Produit.query.get(produit_id)
    if not produit:
        return jsonify({"error": "Produit not found"}), 404

    # Validate type-specific required fields
    required_keys, extractor = _required_type_fields(produit.type)
    missing = [k for k in required_keys if not (data.get(k) or "").strip()]
    if missing:
        return jsonify({"error": f"Missing required fields for '{produit.type}': {', '.join(missing)}"}), 400
    details = extractor(data)

    # Find matching DureeSansStock row (etat 'actif' by default)
    dss = DureeSansStock.query.filter_by(produit_id=produit_id, duree=duree, etat='actif').first()
    if not dss:
        return jsonify({"error": "No matching (produit, duree) found in DureeSansStock"}), 404

    prix_unitaire = _prix_unitaire_for_user(dss, current_user)
    montant = prix_unitaire * quantite

    # Create order
    cmd = CommandeProduit(
        reference=generate_reference(),
        user_id=current_user.id,
        produit_id=produit_id,
        duree=duree,
        quantite=quantite,
        prix_unitaire=prix_unitaire,
        montant=montant,
        nom=nom,
        adresse=adresse,
        telephone=telephone,
        details=details,
        etat=CommandeEtat.EN_ATTENTE,
        paiement=CommandePaiement.IMPAYE
    )
    db.session.add(cmd)
    db.session.commit()

    return jsonify({"message": "Commande créée", "commande": cmd.to_dict()}), 201


@commande_produit_bp.route('/my', methods=['GET'])
@jwt_required()
def my_commandes():
    """
    List user commandes with pagination and filters.
    Query params:
      - search (ref/nom/adresse/telephone/produit_name)
      - produit_id
      - etat
      - page, per_page
    """
    try:
        user_id = get_jwt_identity()
        search = (request.args.get('search') or "").strip().lower()
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        produit_id = request.args.get('produit_id', type=int)
        etat = request.args.get('etat')

        q = CommandeProduit.query.filter_by(user_id=user_id)

        if produit_id:
            q = q.filter(CommandeProduit.produit_id == produit_id)
        if etat:
            q = q.filter(CommandeProduit.etat == etat)

        if search:
            # join to Produit only when searching by produit name
            q = q.join(Produit, CommandeProduit.produit_id == Produit.id).filter(
                or_(
                    func.lower(CommandeProduit.reference).like(f"%{search}%"),
                    func.lower(CommandeProduit.nom).like(f"%{search}%"),
                    func.lower(CommandeProduit.adresse).like(f"%{search}%"),
                    func.lower(CommandeProduit.telephone).like(f"%{search}%"),
                    func.lower(Produit.name).like(f"%{search}%"),
                    cast(CommandeProduit.montant, String).ilike(f"%{search}%"),
                )
            )

        paginated = q.order_by(CommandeProduit.date_creation.desc()).paginate(page=page, per_page=per_page, error_out=False)
        items = [c.to_dict() for c in paginated.items]

        return jsonify({
            "commandes": items,
            "total": paginated.total,
            "page": page,
            "per_page": per_page
        }), 200
    except Exception as e:
        return jsonify({"error": "Unexpected error", "details": str(e)}), 500


# ================================
# MANAGER / ADMIN_BOSS SIDE
# ================================
@commande_produit_bp.route('/', methods=['GET'])
@jwt_required()
def get_all_commandes():
    """
    Manager/Admin_boss: list all commandes with pagination/search/filters.
    Query params:
      - search (ref/nom/adresse/telephone/produit_name)
      - produit_id
      - etat
      - page, per_page
    """
    try:
        current_user = User.query.get(get_jwt_identity())
        if not _is_manager_or_boss(current_user):
            return jsonify({"error": "Access denied"}), 403

        search = (request.args.get('search') or "").strip().lower()
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        produit_id = request.args.get('produit_id', type=int)
        etat = request.args.get('etat')

        q = CommandeProduit.query

        if produit_id:
            q = q.filter(CommandeProduit.produit_id == produit_id)
        if etat:
            q = q.filter(CommandeProduit.etat == etat)

        if search:
            q = q.join(Produit, CommandeProduit.produit_id == Produit.id).filter(
                or_(
                    func.lower(CommandeProduit.reference).like(f"%{search}%"),
                    func.lower(CommandeProduit.nom).like(f"%{search}%"),
                    func.lower(CommandeProduit.adresse).like(f"%{search}%"),
                    func.lower(CommandeProduit.telephone).like(f"%{search}%"),
                    func.lower(Produit.name).like(f"%{search}%"),
                    cast(CommandeProduit.montant, String).ilike(f"%{search}%"),
                    func.lower(CommandeProduit.etat).like(f"%{search}%"),
                    func.lower(CommandeProduit.paiement).like(f"%{search}%"),
                )
            )

        paginated = q.order_by(CommandeProduit.date_creation.desc()).paginate(page=page, per_page=per_page, error_out=False)
        items = [c.to_dict() for c in paginated.items]

        return jsonify({
            "commandes": items,
            "total": paginated.total,
            "page": page,
            "per_page": per_page
        }), 200
    except Exception as e:
        return jsonify({"error": "Unexpected error", "details": str(e)}), 500


@commande_produit_bp.route('/<int:commande_id>/annuler', methods=['PUT'])
@jwt_required()
def annuler_commande(commande_id):
    """Manager/Admin_boss: cancel a commande."""
    current_user = User.query.get(get_jwt_identity())
    if not _is_manager_or_boss(current_user):
        return jsonify({"error": "Access denied"}), 403

    cmd = CommandeProduit.query.get(commande_id)
    if not cmd:
        return jsonify({"error": "Commande not found"}), 404

    cmd.etat = CommandeEtat.ANNULE
    db.session.commit()
    return jsonify({"message": "Commande annulée", "commande": cmd.to_dict()}), 200


@commande_produit_bp.route('/<int:commande_id>/accepter', methods=['PUT'])
@jwt_required()
def accepter_commande(commande_id):
    """
    Manager/Admin_boss: accept a commande and debit user's solde.
    Moves etat -> ENCOURS, paiement remains IMPAYE.
    """
    current_user = User.query.get(get_jwt_identity())
    if not _is_manager_or_boss(current_user):
        return jsonify({"error": "Access denied"}), 403

    cmd = CommandeProduit.query.get(commande_id)
    if not cmd:
        return jsonify({"error": "Commande not found"}), 404

    if cmd.etat != CommandeEtat.EN_ATTENTE:
        return jsonify({"error": "Commande must be en_attente to accept"}), 400

    buyer = User.query.get(cmd.user_id)
    if not buyer:
        return jsonify({"error": "Buyer not found"}), 404

    if float(buyer.solde) < float(cmd.montant):
        return jsonify({"error": "Solde insuffisant"}), 400

    buyer.solde = float(buyer.solde) - float(cmd.montant)
    cmd.etat = CommandeEtat.ENCOURS
    cmd.paiement = CommandePaiement.IMPAYE
    db.session.commit()

    return jsonify({"message": "Commande acceptée et solde débité", "commande": cmd.to_dict(), "buyer_new_solde": float(buyer.solde)}), 200


@commande_produit_bp.route('/<int:commande_id>/confirmer', methods=['PUT'])
@jwt_required()
def confirmer_commande(commande_id):
    """
    Manager/Admin_boss: confirm a commande (after delivery), mark as PAYE.
    Moves etat -> CONFIRME, paiement -> PAYE.
    """
    current_user = User.query.get(get_jwt_identity())
    if not _is_manager_or_boss(current_user):
        return jsonify({"error": "Access denied"}), 403

    cmd = CommandeProduit.query.get(commande_id)
    if not cmd:
        return jsonify({"error": "Commande not found"}), 404

    if cmd.etat != CommandeEtat.ENCOURS:
        return jsonify({"error": "Commande must be en cours to confirm"}), 400

    cmd.etat = CommandeEtat.CONFIRME
    cmd.paiement = CommandePaiement.PAYE
    db.session.commit()

    return jsonify({"message": "Commande confirmée et payée", "commande": cmd.to_dict()}), 200


@commande_produit_bp.route('/<int:commande_id>', methods=['DELETE'])
@jwt_required()
def delete_commande(commande_id):
    """Manager/Admin_boss: delete a commande."""
    try:
        current_user = User.query.get(get_jwt_identity())
        if not _is_manager_or_boss(current_user):
            return jsonify({"error": "Access denied"}), 403

        cmd = CommandeProduit.query.get(commande_id)
        if not cmd:
            return jsonify({"error": "Commande not found"}), 404

        db.session.delete(cmd)
        db.session.commit()
        return jsonify({"message": "Commande deleted successfully", "commande_id": commande_id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Unexpected error", "details": str(e)}), 500

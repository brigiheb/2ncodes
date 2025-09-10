# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from .. import db
from ..models.commande_boutique import CommandeBoutique, CommandeEtat, CommandePaiement
from ..models.article import Article
from ..models.user import User
import uuid

commandes_bp = Blueprint('commandes', __name__, url_prefix='/commandes')

def generate_reference():
    """Generate a unique order reference."""
    return f"CMD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

# ================================
# USER SIDE
# ================================
@commandes_bp.route('/checkout', methods=['POST'])
@jwt_required()
def checkout():
    """
    User checkout: create a new commande from panier/article selection.
    Expected form data: article_id, quantite, nom, adresse, telephone
    """
    user_id = get_jwt_identity()
    data = request.json or request.form

    article_id = data.get("article_id")
    quantite = int(data.get("quantite", 1))
    nom = data.get("nom")
    adresse = data.get("adresse")
    telephone = data.get("telephone")

    if not all([article_id, quantite, nom, adresse, telephone]):
        return jsonify({"error": "All fields are required"}), 400

    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "Article not found"}), 404

    montant = (article.prix_1 or 0) * quantite

    commande = CommandeBoutique(
        reference=generate_reference(),
        user_id=user_id,
        article_id=article_id,
        quantite=quantite,
        montant=montant,
        nom=nom,
        adresse=adresse,
        telephone=telephone,
        etat=CommandeEtat.EN_ATTENTE,
        paiement=CommandePaiement.IMPAYE
    )
    db.session.add(commande)
    db.session.commit()

    return jsonify({"message": "Commande created successfully", "commande": commande.to_dict()}), 201

@commandes_bp.route('/my', methods=['GET'])
@jwt_required()
def my_commandes():
    """List commandes of the current user with pagination, search, and article_id filter."""
    try:
        user_id = get_jwt_identity()
        search_query = request.args.get('search', type=str, default="").strip().lower()
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        article_id = request.args.get('article_id', type=int, default=None)

        # Base query filtering by user_id
        query = CommandeBoutique.query.filter_by(user_id=user_id)

        # Apply article_id filter
        if article_id is not None:
            query = query.filter(CommandeBoutique.article_id == article_id)

        # Apply search with join to Article table
        if search_query:
            query = query.join(Article, CommandeBoutique.article_id == Article.id).filter(
                db.or_(
                    CommandeBoutique.reference.ilike(f"%{search_query}%"),
                    CommandeBoutique.nom.ilike(f"%{search_query}%"),
                    CommandeBoutique.adresse.ilike(f"%{search_query}%"),
                    CommandeBoutique.telephone.ilike(f"%{search_query}%"),
                    CommandeBoutique.montant.ilike(f"%{search_query}%"),
                    CommandeBoutique.etat.ilike(f"%{search_query}%"),
                    CommandeBoutique.paiement.ilike(f"%{search_query}%"),
                    CommandeBoutique.date_creation.ilike(f"%{search_query}%"),
                    Article.nom.ilike(f"%{search_query}%")  
                )
            )
        else:
            # Avoid unnecessary join if no search query
            query = query

        # Apply sorting and pagination
        paginated = query.order_by(CommandeBoutique.date_creation.desc()).paginate(page=page, per_page=per_page, error_out=False)
        commandes = paginated.items

        return jsonify({
            "commandes": [c.to_dict() for c in commandes],
            "total": paginated.total,
            "page": page,
            "per_page": per_page
        }), 200

    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

# ================================
# MANAGER / ADMIN BOSS SIDE
# ================================
def is_manager_or_boss(user):
    return user.role in ["manager", "admin_boss"]

@commandes_bp.route('/', methods=['GET'])
@jwt_required()
def get_all_commandes():
    """Manager/admin: list all commandes with pagination, search, and article_id filter."""
    try:
        user = User.query.get(get_jwt_identity())
        if not is_manager_or_boss(user):
            return jsonify({"error": "Access denied"}), 403

        search_query = request.args.get('search', type=str, default="").strip().lower()
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        article_id = request.args.get('article_id', type=int, default=None)

        # Base query
        query = CommandeBoutique.query

        # Apply article_id filter
        if article_id is not None:
            query = query.filter(CommandeBoutique.article_id == article_id)

        # Apply search with join to Article table
        if search_query:
            query = query.join(Article, CommandeBoutique.article_id == Article.id).filter(
                db.or_(
                    CommandeBoutique.reference.ilike(f"%{search_query}%"),
                    CommandeBoutique.nom.ilike(f"%{search_query}%"),
                    CommandeBoutique.adresse.ilike(f"%{search_query}%"),
                    CommandeBoutique.telephone.ilike(f"%{search_query}%"),
                    CommandeBoutique.etat.ilike(f"%{search_query}%"),
                    CommandeBoutique.montant.ilike(f"%{search_query}%"),
                    CommandeBoutique.paiement.ilike(f"%{search_query}%"),
                    Article.nom.ilike(f"%{search_query}%")  
                )
            )
        else:
            # Avoid unnecessary join if no search query
            query = query

        # Apply sorting and pagination
        paginated = query.order_by(CommandeBoutique.date_creation.desc()).paginate(page=page, per_page=per_page, error_out=False)
        commandes = paginated.items

        return jsonify({
            "commandes": [c.to_dict() for c in commandes],
            "total": paginated.total,
            "page": page,
            "per_page": per_page
        }), 200

    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@commandes_bp.route('/<int:commande_id>/annuler', methods=['PUT'])
@jwt_required()
def annuler_commande(commande_id):
    """Manager/admin: cancel a commande."""
    user = User.query.get(get_jwt_identity())
    if not is_manager_or_boss(user):
        return jsonify({"error": "Access denied"}), 403

    commande = CommandeBoutique.query.get(commande_id)
    if not commande:
        return jsonify({"error": "Commande not found"}), 404

    commande.etat = CommandeEtat.ANNULE
    db.session.commit()
    return jsonify({"message": "Commande annulée", "commande": commande.to_dict()}), 200

@commandes_bp.route('/<int:commande_id>/accepter', methods=['PUT'])
@jwt_required()
def accepter_commande(commande_id):
    """Manager/admin: accept a commande and debit user solde."""
    user = User.query.get(get_jwt_identity())
    if not is_manager_or_boss(user):
        return jsonify({"error": "Access denied"}), 403

    commande = CommandeBoutique.query.get(commande_id)
    if not commande:
        return jsonify({"error": "Commande not found"}), 404

    if commande.etat != CommandeEtat.EN_ATTENTE:
        return jsonify({"error": "Commande must be en_attente to accept"}), 400

    user_client = User.query.get(commande.user_id)
    if user_client.solde < commande.montant:
        return jsonify({"error": "Solde insuffisant"}), 400

    # Debit solde
    user_client.solde -= commande.montant
    commande.etat = CommandeEtat.ENCOURS
    commande.paiement = CommandePaiement.IMPAYE

    db.session.commit()
    return jsonify({"message": "Commande acceptée et solde débité", "commande": commande.to_dict()}), 200

@commandes_bp.route('/<int:commande_id>/confirmer', methods=['PUT'])
@jwt_required()
def confirmer_commande(commande_id):
    """Manager/admin: confirm a commande after delivery, mark as payée."""
    user = User.query.get(get_jwt_identity())
    if not is_manager_or_boss(user):
        return jsonify({"error": "Access denied"}), 403

    commande = CommandeBoutique.query.get(commande_id)
    if not commande:
        return jsonify({"error": "Commande not found"}), 404

    if commande.etat != CommandeEtat.ENCOURS:
        return jsonify({"error": "Commande must be en cours to confirm"}), 400

    commande.etat = CommandeEtat.CONFIRME
    commande.paiement = CommandePaiement.PAYE

    db.session.commit()
    return jsonify({"message": "Commande confirmée et payée", "commande": commande.to_dict()}), 200

@commandes_bp.route('/<int:commande_id>', methods=['DELETE'])
@jwt_required()
def delete_commande(commande_id):
    """Manager/admin: delete a commande."""
    try:
        user = User.query.get(get_jwt_identity())
        if not is_manager_or_boss(user):
            return jsonify({"error": "Access denied"}), 403

        commande = CommandeBoutique.query.get(commande_id)
        if not commande:
            return jsonify({"error": "Commande not found"}), 404

        db.session.delete(commande)
        db.session.commit()
        return jsonify({"message": "Commande deleted successfully", "commande_id": commande_id}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500
# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename

from .. import db
from ..models.boutique import Boutique
import os


boutiques_bp = Blueprint('boutiques', __name__, url_prefix='/boutiques')


@boutiques_bp.route('/get_boutiques', methods=['GET'])
def get_all_boutiques():
    """
    Retrieve boutiques, sorted by ID descending, with optional filtering, search, and pagination.
    If page and per_page are not provided, return all boutiques without pagination.
    """
    try:
        search_query = request.args.get('search', type=str, default="").strip().lower()
        page = request.args.get('page', type=int, default=None)
        per_page = request.args.get('per_page', type=int, default=None)

        # Collect filters (excluding 'search', 'page', and 'per_page')
        filters = {
            key: value for key, value in request.args.items()
            if key not in ['search', 'page', 'per_page']
        }

        query = Boutique.query

        # Apply filters
        for field, value in filters.items():
            if hasattr(Boutique, field):
                query = query.filter(getattr(Boutique, field).like(f"%{value}%"))

        # Apply search (on nom)
        if search_query:
            query = query.filter(
                Boutique.nom.ilike(f"%{search_query}%")
            )

        # Apply descending sort
        query = query.order_by(Boutique.id.desc())

        # If page or per_page is not provided, return all boutiques
        if page is None or per_page is None:
            boutiques = query.all()
            return jsonify({
                "page": 1,  # Default for non-paginated response
                "per_page": len(boutiques),  # Total count for non-paginated
                "total": len(boutiques),
                "pages": 1,
                "boutiques": [boutique.to_dict() for boutique in boutiques]
            }), 200

        # Apply pagination
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        boutiques = paginated.items

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "boutiques": [boutique.to_dict() for boutique in boutiques]
        }), 200

    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@boutiques_bp.route('/get_boutique/<int:boutique_id>', methods=['GET'])
def get_boutique(boutique_id):
    """Get a single boutique by ID."""
    boutique = Boutique.query.get(boutique_id)
    if not boutique:
        return jsonify({"error": f"Boutique with id {boutique_id} not found"}), 404
    return jsonify(boutique.to_dict()), 200


@boutiques_bp.route('/add_boutique', methods=['POST'])
def add_boutique():
    nom = request.form.get('nom')
    photo_file = request.files.get('photo')

    if not nom:
        return jsonify({"error": "Name is required"}), 400

    if Boutique.query.filter_by(nom=nom).first():
        return jsonify({"error": "Boutique with this name already exists"}), 400

    new_boutique = Boutique(nom=nom)
    db.session.add(new_boutique)
    db.session.flush()  # Get new_boutique.id before commit

    # Save photo if provided
    if photo_file and photo_file.filename:
        folder = os.path.join(
            current_app.root_path,
            'static',
            'boutiques_images',
            nom.lower().replace(" ", "_")
        )
        os.makedirs(folder, exist_ok=True)

        filename = f"{new_boutique.id}.png"
        save_path = os.path.join(folder, filename)

        if os.path.exists(save_path):
            os.remove(save_path)

        photo_file.save(save_path)
        relative_path = os.path.relpath(save_path, current_app.root_path)
        new_boutique.photo = relative_path

    db.session.commit()
    return jsonify(new_boutique.to_dict()), 201

@boutiques_bp.route('/put_boutique/<int:boutique_id>', methods=['PUT'])
def update_boutique(boutique_id):
    boutique = Boutique.query.get(boutique_id)
    if not boutique:
        return jsonify({"error": f"Boutique with id {boutique_id} not found"}), 404

    nom = request.form.get('nom', boutique.nom)
    photo_file = request.files.get('photo')

    boutique.nom = nom

    if photo_file and photo_file.filename:
        folder = os.path.join(
            current_app.root_path,
            'static',
            'boutiques_images',
            nom.lower().replace(" ", "_")
        )
        os.makedirs(folder, exist_ok=True)

        filename = f"{boutique.id}.png"
        save_path = os.path.join(folder, filename)

        if os.path.exists(save_path):
            os.remove(save_path)

        photo_file.save(save_path)
        boutique.photo = os.path.relpath(save_path, current_app.root_path)

    db.session.commit()
    return jsonify(boutique.to_dict()), 200



@boutiques_bp.route('/delete_boutique/<int:boutique_id>', methods=['DELETE'])
def delete_boutique(boutique_id):
    """Delete a boutique."""
    boutique = Boutique.query.get(boutique_id)
    if not boutique:
        return jsonify({"error": f"Boutique with id {boutique_id} not found"}), 404

    db.session.delete(boutique)
    db.session.commit()

    return jsonify({"message": f"Boutique with id {boutique_id} has been deleted"}), 200

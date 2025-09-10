# -*- coding: utf-8 -*-
import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from ..models.application import Application
from ..models.user import User
from ..models.visible_item import VisibleItem, ItemType
from .. import db
from sqlalchemy.exc import SQLAlchemyError

applications_bp = Blueprint('applications', __name__)

def add_application_to_all_users_visible_items(application_id):
    users = User.query.all()
    for user in users:
        visible_item = VisibleItem(
            user_id=user.id,
            item_id=application_id,
            item_type=ItemType.application
        )
        db.session.add(visible_item)
    db.session.commit()

@applications_bp.route('/add_application', methods=['POST'])
def add_application():
    """Create a new application with optional logo upload."""
    try:
        nom = request.form.get('nom')
        lien = request.form.get('lien')
        logo_file = request.files.get('logo')

        if not nom or not lien:
            return jsonify({"error": "Fields 'nom' and 'lien' are required"}), 400

        clean_nom = nom.strip().lower().replace(" ", "_")
        new_application = Application(nom=nom.strip(), lien=lien.strip())
        db.session.add(new_application)
        db.session.flush()  # Get the new application ID before commit

        if logo_file and logo_file.filename:
            folder = os.path.join(
                current_app.root_path,
                'static',
                'applications_logos',
                clean_nom
            )
            os.makedirs(folder, exist_ok=True)
            filename = secure_filename(f"{new_application.id}.png")
            save_path = os.path.join(folder, filename)

            if os.path.exists(save_path):
                os.remove(save_path)

            logo_file.save(save_path)
            new_application.logo = os.path.relpath(save_path, current_app.root_path)

        db.session.commit()

        # Add the new application to all users' visible items
        add_application_to_all_users_visible_items(new_application.id)
        print(f"[SUCCESS] Added application {new_application.id} to all users' visible items")

        return jsonify({
            "message": "Application added successfully",
            "application": new_application.to_dict()
        }), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@applications_bp.route('/get_applications', methods=['GET'])
def get_all_applications():
    """
    Retrieve applications with optional pagination, filtering, and search.
    Returns all applications if no pagination parameters are provided.
    """
    try:
        search_query = request.args.get('search', type=str, default="").strip().lower()
        page = request.args.get('page', type=int, default=None)
        per_page = request.args.get('per_page', type=int, default=None)
        filters = {
            key: value for key, value in request.args.items()
            if key not in ['search', 'page', 'per_page']
        }

        query = Application.query

        # Apply filters dynamically
        for field, value in filters.items():
            if hasattr(Application, field):
                query = query.filter(getattr(Application, field).ilike(f"%{value}%"))

        # Apply search on 'nom' and 'lien'
        if search_query:
            query = query.filter(
                db.or_(
                    Application.nom.ilike(f"%{search_query}%"),
                    Application.lien.ilike(f"%{search_query}%")
                )
            )

        # If no pagination parameters are provided, return all results
        if page is None and per_page is None:
            applications = query.order_by(Application.id.desc()).all()
            return jsonify({
                "total": len(applications),
                "applications": [app.to_dict() for app in applications]
            }), 200

        # Apply pagination if parameters are provided
        per_page = per_page or 20  # Default to 20 if not specified
        page = page or 1           # Default to 1 if not specified
        paginated = query.order_by(Application.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
        applications = paginated.items

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "applications": [app.to_dict() for app in applications]
        }), 200

    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@applications_bp.route('/get_application/<int:id>', methods=['GET'])
def get_application_by_id(id):
    """Retrieve a single application by its ID."""
    try:
        application = Application.query.get(id)
        if application:
            return jsonify(application.to_dict())
        return jsonify({"message": "Application not found"}), 404
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@applications_bp.route('/update_application/<int:id>', methods=['PUT'])
def update_application(id):
    """Update an application, including its logo if uploaded."""
    try:
        application = Application.query.get(id)
        if not application:
            return jsonify({"message": "Application not found"}), 404

        nom = request.form.get('nom', application.nom)
        lien = request.form.get('lien', application.lien)
        logo_file = request.files.get('logo')

        clean_nom = nom.strip().lower().replace(" ", "_")
        application.nom = nom.strip()
        application.lien = lien.strip()

        if logo_file and logo_file.filename:
            folder = os.path.join(
                current_app.root_path,
                'static',
                'applications_logos',
                clean_nom
            )
            os.makedirs(folder, exist_ok=True)
            filename = secure_filename(f"{application.id}.png")
            save_path = os.path.join(folder, filename)

            if os.path.exists(save_path):
                os.remove(save_path)

            logo_file.save(save_path)
            application.logo = os.path.relpath(save_path, current_app.root_path)

        db.session.commit()
        return jsonify({
            "message": "Application updated successfully",
            "application": application.to_dict()
        }), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@applications_bp.route('/delete_application/<int:id>', methods=['DELETE'])
def delete_application(id):
    """Delete an application and its associated logo if exists."""
    try:
        application = Application.query.get(id)
        if not application:
            return jsonify({"message": "Application not found"}), 404

        # Delete associated logo if it exists
        if application.logo:
            logo_path = os.path.join(current_app.root_path, application.logo)
            if os.path.isfile(logo_path):
                try:
                    os.remove(logo_path)
                except Exception as e:
                    print(f"[WARNING] Failed to delete logo: {e}")

        db.session.delete(application)
        db.session.commit()
        return jsonify({"message": "Application deleted successfully"}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500
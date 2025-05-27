# -*- coding: utf-8 -*-
import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from ..models.application import Application
from .. import db
from sqlalchemy.exc import SQLAlchemyError

applications_bp = Blueprint('applications', __name__)

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
    """Retrieve all applications."""
    try:
        applications = Application.query.all()
        result = [app.to_dict() for app in applications]
        return jsonify(result)
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
    """Delete an application."""
    try:
        application = Application.query.get(id)
        if not application:
            return jsonify({"message": "Application not found"}), 404

        db.session.delete(application)
        db.session.commit()
        return jsonify({"message": "Application deleted successfully"})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

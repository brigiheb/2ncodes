# -*- coding: utf-8 -*-
import os
from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename
from .. import db
from ..models.article import Article
from ..models.boutique import Boutique
articles_bp = Blueprint('articles', __name__, url_prefix='/articles')

@articles_bp.route('/get_articles', methods=['GET'])
def get_all_articles():
    """
    Retrieve paginated articles, sorted by ID descending,
    with optional filtering by etat and search.
    """
    try:
        search_query = request.args.get('search', type=str, default="").strip().lower()
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        etat = request.args.get('etat', type=str, default="").strip().lower()

        query = Article.query

        # Apply etat filter
        if etat in ['actif', 'inactif']:
            query = query.filter(Article.etat == etat)

        # Apply search
        if search_query:
            query = query.filter(
                db.or_(
                    Boutique.nom.ilike(f"%{search_query}%"),
                    Article.nom.ilike(f"%{search_query}%"),
                    Article.description.ilike(f"%{search_query}%"),
                    Article.prix_1.ilike(f"%{search_query}%"),
                    Article.prix_2.ilike(f"%{search_query}%"),
                    Article.prix_3.ilike(f"%{search_query}%"),
                )
            )

        # Apply sorting and pagination
        paginated = query.order_by(Article.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
        articles = paginated.items

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "articles": [article.to_dict() for article in articles]
        }), 200

    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500
    

@articles_bp.route('/get_articles_by_category/<int:boutique_id>', methods=['GET'])
def get_articles_by_category(boutique_id):
    """
    Retrieve paginated articles filtered by boutique_id, sorted by ID descending,
    with optional filtering by etat and search.
    """
    try:
        search_query = request.args.get('search', type=str, default="").strip().lower()
        page = request.args.get('page', type=int, default=1)
        per_page = request.args.get('per_page', type=int, default=20)
        etat = request.args.get('etat', type=str, default="").strip().lower()

        # Base query filtering by Article.boutique_id
        query = Article.query.filter(Article.boutique_id == boutique_id)

        # Apply etat filter
        if etat in ['actif', 'inactif']:
            query = query.filter(Article.etat == etat)

        # Apply search
        if search_query:
            query = query.join(Boutique).filter(
                db.or_(
                    Boutique.nom.ilike(f"%{search_query}%"),
                    Article.nom.ilike(f"%{search_query}%"),
                    Article.description.ilike(f"%{search_query}%"),
                    Article.prix_1.ilike(f"%{search_query}%"),
                    Article.prix_2.ilike(f"%{search_query}%"),
                    Article.prix_3.ilike(f"%{search_query}%"),
                )
            )

        # Apply sorting and pagination
        paginated = query.order_by(Article.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
        articles = paginated.items

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "articles": [article.to_dict() for article in articles]
        }), 200

    except Exception as e:
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500        

@articles_bp.route('/get_article/<int:article_id>', methods=['GET'])
def get_article(article_id):
    """Retrieve a single article by ID."""
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": f"Article with id {article_id} not found"}), 404
    return jsonify(article.to_dict()), 200

@articles_bp.route('/add_article', methods=['POST'])
def add_article():
    nom = request.form.get('nom')
    description = request.form.get('description')
    prix_1 = request.form.get('prix_1')
    prix_2 = request.form.get('prix_2')
    prix_3 = request.form.get('prix_3')
    etat = request.form.get('etat')
    boutique_id = request.form.get('boutique_id')
    photo_file = request.files.get('photo')

    boutique = Boutique.query.get(boutique_id)
    if not boutique:
        return jsonify({"error": f"Boutique with id {boutique_id} not found"}), 404

    new_article = Article(
        boutique_id=boutique_id,
        nom=nom,
        description=description,
        prix_1=prix_1,
        prix_2=prix_2,
        prix_3=prix_3,
        etat=etat
    )
    db.session.add(new_article)
    db.session.flush()  # Get new_article.id before saving file

    if photo_file and photo_file.filename:
        folder = os.path.join(
            current_app.root_path,
            'static',
            'articles_images',
            nom.lower().replace(" ", "_")
        )
        os.makedirs(folder, exist_ok=True)

        filename = f"{new_article.id}.png"
        save_path = os.path.join(folder, filename)

        if os.path.exists(save_path):
            os.remove(save_path)

        photo_file.save(save_path)
        new_article.photo = os.path.relpath(save_path, current_app.root_path)

    db.session.commit()
    return jsonify(new_article.to_dict()), 201

@articles_bp.route('/update_article/<int:article_id>', methods=['PUT'])
def update_article(article_id):
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": f"Article with id {article_id} not found"}), 404

    nom = request.form.get('nom', article.nom)
    description = request.form.get('description', article.description)
    prix_1 = request.form.get('prix_1', article.prix_1)
    prix_2 = request.form.get('prix_2', article.prix_2)
    prix_3 = request.form.get('prix_3', article.prix_3)
    etat = request.form.get('etat', article.etat)
    new_boutique_id = request.form.get('boutique_id', article.boutique_id)
    photo_file = request.files.get('photo')

    # Validate new boutique
    if str(new_boutique_id) != str(article.boutique_id):
        boutique = Boutique.query.get(new_boutique_id)
        if not boutique:
            return jsonify({"error": f"Boutique with id {new_boutique_id} not found"}), 404
        article.boutique_id = new_boutique_id

    article.nom = nom
    article.description = description
    article.prix_1 = prix_1
    article.prix_2 = prix_2
    article.prix_3 = prix_3
    article.etat = etat

    if photo_file and photo_file.filename:
        folder = os.path.join(
            current_app.root_path,
            'static',
            'articles_images',
            nom.lower().replace(" ", "_")
        )
        os.makedirs(folder, exist_ok=True)

        filename = f"{article.id}.png"
        save_path = os.path.join(folder, filename)

        if os.path.exists(save_path):
            os.remove(save_path)

        photo_file.save(save_path)
        article.photo = os.path.relpath(save_path, current_app.root_path)

    db.session.commit()
    return jsonify(article.to_dict()), 200


@articles_bp.route('/delete_article/<int:article_id>', methods=['DELETE'])
def delete_article(article_id):
    """Delete an article."""
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": f"Article with id {article_id} not found"}), 404

    db.session.delete(article)
    db.session.commit()
    return jsonify({"message": f"Article with id {article_id} has been deleted"}), 200

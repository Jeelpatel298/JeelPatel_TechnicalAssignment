import os
import secrets
from datetime import date, datetime, timezone
from hmac import compare_digest

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from flask.json.provider import DefaultJSONProvider
from pymysql.err import OperationalError
from werkzeug.exceptions import HTTPException

from . import db
from .routes import api, register_cli
from .validation import Problem


class ISOJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(value):
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
        if isinstance(value, date):
            return value.isoformat()
        return DefaultJSONProvider.default(value)


def create_app(config=None):
    app = Flask(__name__)
    app.json = ISOJSONProvider(app)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        DATABASE={
            "host": os.getenv("DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("DB_PORT", 3306)),
            "user": os.getenv("DB_USER", "inventory_app"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv("DB_NAME", "sales_inventory"),
        },
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE") == "1",
        MAX_CONTENT_LENGTH=1_048_576,
    )
    if config:
        app.config.update(config)
    if not app.secret_key or len(app.secret_key) < 32:
        raise RuntimeError("Set SECRET_KEY to a random value of at least 32 characters.")

    app.teardown_appcontext(db.close)
    app.register_blueprint(api)
    register_cli(app)

    @app.before_request
    def identify_user():
        if request.endpoint == "static":
            return
        user_id = session.get("user_id")
        g.user = db.query("SELECT id,name,email,role FROM users WHERE id=%s", (user_id,),
                          one=True) if user_id else None
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.endpoint != "api.login" and request.path.startswith("/api/") and not g.user:
                raise Problem("Sign in to continue.", 401)
            supplied = request.headers.get("X-CSRF-Token", "")
            expected = session.get("csrf", "")
            if not expected or not supplied.isascii() or not compare_digest(supplied, expected):
                raise Problem("Invalid or expired security token. Reload and try again.", 403)

    @app.after_request
    def browser_headers(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.get("/")
    def home():
        if g.user is None:
            return redirect(url_for("signin"))
        return render_template("dashboard.html", user=g.user, csrf=csrf_token(),
                               today=datetime.now(timezone.utc).date().isoformat())

    @app.get("/login")
    def signin():
        if g.user:
            return redirect(url_for("home"))
        return render_template("login.html", csrf=csrf_token())

    @app.errorhandler(Problem)
    def business_error(error):
        body = {"error": str(error)}
        if error.errors is not None:
            body["errors"] = error.errors
        return jsonify(body), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        response = error.get_response()
        response.set_data(app.json.dumps({"error": error.description}))
        response.mimetype = "application/json"
        return response

    @app.errorhandler(OperationalError)
    def database_error(error):
        if error.args[0] in (1205, 1213):
            return jsonify(error="A concurrent update interrupted the request. Please retry."), 409
        app.logger.error("Database operation failed with code %s", error.args[0])
        return jsonify(error="Database temporarily unavailable."), 503

    @app.errorhandler(500)
    def unexpected_error(_error):
        return jsonify(error="The server could not complete the request."), 500

    return app


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]

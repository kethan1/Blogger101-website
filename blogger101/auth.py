from blogger101.app_extensions import mongo, flask_bcrypt


def logged_in(session):
    return "logged_in" in session and session["logged_in"] not in (None, {})


def check_login(email: str, password: str) -> dict:
    user = mongo.db.users.find_one({"email": email})
    if user is None:
        return {"error": True, "message": "A User With That Email Was Not Found"}
    if flask_bcrypt.check_password_hash(user["password"], password):
        return {"error": False, "message": "Success", "user": user}
    return {"error": True, "message": "Incorrect Password"}

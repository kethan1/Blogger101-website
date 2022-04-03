import datetime
import base64
import json
import os

from flask import (
    Flask,
    render_template,
    redirect,
    flash,
    abort,
    request,
    Markup,
    session,
    jsonify,
    url_for,
)
from flask_pymongo import PyMongo
from flask_compress import Compress
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from werkzeug.exceptions import HTTPException
from bson.objectid import ObjectId
from dotenv import load_dotenv
from urllib.parse import quote
import pyimgur
from itsdangerous import URLSafeTimedSerializer

import http_response_codes as status
import email_oauth


app = Flask(__name__)
app.url_map.strict_slashes = False

if "DYNO" not in os.environ:
    load_dotenv()

app.config.update(
    IMGUR_ID=os.environ["IMGUR_ID"],
    MONGO_URI=os.environ["MONGO_URI"],
    SECRET_KEY=os.environ["SECRET_KEY"],
    EMAIL_USERNAME="Blogger101 Bot",
    EMAIL_SENDER=os.environ["EMAIL_ADDRESS"],
    EMAIL_TOKEN=json.loads(os.environ["EMAIL_TOKEN"]),
)

app.config["ImgurObject"] = pyimgur.Imgur(app.config["IMGUR_ID"])
mongo = PyMongo(app)
flask_bcrypt = Bcrypt(app)
Compress(app)
cors = CORS(app, resources={"/api/*": {"origins": "*"}})

email_url_generator = URLSafeTimedSerializer(app.config["SECRET_KEY"])

email_oauth_credentials = email_oauth.load_credentials_from_dict(
    app.config["EMAIL_TOKEN"]
)


@app.before_request
def before_request():
    if "DYNO" in os.environ and request.url.startswith("http://"):
        url = request.url.replace("http://", "https://", 1)
        return redirect(quote(url), code=301)


def logged_in(session):
    return "logged_in" in session and session["logged_in"] not in (None, {})


@app.route("/")
def blogs():
    return render_template(
        "blogs.html",
        login_status=((session["logged_in"] if logged_in(session) else None)),
    )


@app.route("/post_blog")
def post_blog():
    if logged_in(session):
        return render_template("post_blog.html", login_status=session["logged_in"])
    flash(
        Markup(
            """Please <a style="text-decoration: underline;" href="/login">Login</a> or <a style="text-decoration: underline;" href="/sign_up">Sign Up</a> to Post a Blog"""
        )
    )
    return redirect("/")


@app.route("/blog/<page>/")
def return_blog(page):
    results = mongo.db.blogs.find_one({"name": f"{page}.html"})
    if results is None:
        abort(404)
    elif "logged_in" not in session or session["logged_in"] is None:
        return render_template("blog_template.html", results=results, login_status=None)
    else:
        results["text"] = Markup(results["text"])
        return render_template(
            "blog_template.html", results=results, login_status=session["logged_in"]
        )


@app.route("/user/<user>/")
def return_use(user):
    results = mongo.db.users.find_one({"username": user})
    if logged_in(session):
        return render_template(
            "user_template.html",
            results_from_user=results,
            login_status=session["logged_in"],
        )
    else:
        return render_template(
            "user_template.html", results_from_user=results, login_status=None
        )


@app.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    if logged_in(session):
        flash("Already Logged In")
        return redirect("/")
    if request.method == "GET":
        return render_template("sign_up.html", login_status=None)
    elif request.method == "POST":
        if request.form["password"] == request.form["confirm_password"]:
            doc = {
                "first_name": request.form.get("first_name"),
                "last_name": request.form.get("last_name"),
                "username": request.form.get("username"),
                "email": request.form.get("email").lower(),
                "password": flask_bcrypt.generate_password_hash(
                    request.form.get("password")
                ).decode(),
            }

            if mongo.db.users.find_one({"email": doc["email"]}) is None:
                token = email_url_generator.dumps(doc["email"], "email-confirm")
                confirm_link = url_for("confirm_email", token=token, _external=True)
                print(confirm_link)
                email_oauth.send_message(
                    email_oauth_credentials,
                    email_oauth.create_message(
                        "Blogger101 <blogger101.bot@gmail.com>",
                        doc["email"],
                        "Blogger101 Email Confirmation",
                        f"Go to {confirm_link} to verify your email",
                        f"<a href='{confirm_link}'>Verify Email<a>",
                    ),
                )

                mongo.db.unverified_users.insert_one(doc)

                return redirect(f"/verify_email/{token}")
            else:
                flash("An Account is Already Registered with that Email")
                return redirect("/sign_up")
        else:
            flash("Confirm Password Does Not Match Password")
            return redirect("/sign_up")


@app.route("/confirm/<token>")
def confirm_email(token):
    email = email_url_generator.loads(token, salt="email-confirm", max_age=3600)
    unverified_user = mongo.db.unverified_users.find_one({"email": email})
    if unverified_user is not None:
        mongo.db.users.insert_one(unverified_user)
        mongo.db.unverified_users.remove(unverified_user)

        session["logged_in"] = {
            "first_name": unverified_user["first_name"],
            "last_name": unverified_user["last_name"],
            "email": unverified_user["email"],
            "username": unverified_user["username"],
        }

        flash("Successfully Signed Up")
        return redirect("/")
    else:
        abort(404)


@app.route("/verify_email/<token>")
def verify_email(token):
    email = email_url_generator.loads(token, salt="email-confirm", max_age=3600)
    return render_template("verify_email.html", login_status=None, email=email)


@app.route("/login", methods=["GET", "POST"])
def login():
    if logged_in(session):
        flash("Already Logged In")
        return redirect("/")

    if request.method == "GET":
        return render_template("login.html", login_status=None)
    elif request.method == "POST":
        doc = {
            "email": request.form.get("email").lower(),
            "password": request.form.get("password"),
        }
        found = mongo.db.users.find_one({"email": doc["email"]})
        if flask_bcrypt.check_password_hash(found["password"], doc["password"]):
            session["logged_in"] = {
                "first_name": found["first_name"],
                "last_name": found["last_name"],
                "email": found["email"],
                "username": found["username"],
            }
            flash("Successfully Logged In")
            return redirect("/")
        else:
            flash("Incorrect Email or Password")
            return redirect("/login")


@app.route("/logout")
def logout():
    if logged_in(session):
        session["logged_in"] = None
        flash("Successfully Logged Out")
    else:
        flash("Not Logged In")

    return redirect("/")


@app.route("/api/v1/blogs")
def api_blogs():
    to_return = []
    for blog in sorted(
        list(mongo.db.blogs.find({})),
        key=lambda date: datetime.datetime.strptime(
            date["date_released"] + date["time_released"], "%m/%d/20%y%H:%M:%S:%f"
        ),
        reverse=True,
    ):
        blog["_id"] = str(blog["_id"])
        blog["link"] = f"https://blogger-101.herokuapp.com/{blog['link']}"
        to_return.append(blog)
    return jsonify(to_return)


@app.route("/api/v1/post-blog", methods=["POST"])
def api_post_blog():
    title = request.form.get("blog_title")
    name = ("_".join(title.split(" "))).lower()
    to_upload_image = app.config["ImgurObject"]._send_request(
        "https://api/v1.imgur.com/3/image",
        method="POST",
        params={"image": base64.b64encode(request.files["file"].read())},
    )
    doc = {
        "title": title,
        "user": request.form.get("user"),
        "name": f"{name}.html",
        "text": request.form.get("blog_content"),
        "link": f"/blog/{name}",
        "date_released": datetime.datetime.utcnow().strftime("%m/%d/%Y"),
        "time_released": datetime.datetime.utcnow().strftime("%H:%M:%S:%f"),
        "comments": [],
        "image": to_upload_image["link"],
    }

    mongo.db.blogs.insert_one(doc)
    return redirect("/")


@app.route("/api/v1/check-user", methods=["POST"])
def check_user():
    email = (request.json["email"]).lower()
    password = request.json["password"]

    user_found = mongo.db.users.find_one({"email": email, "password": password})

    if user_found is not None:
        return {"found": True, "user_found": user_found["username"]}
    else:
        return {"found": False}, status.USER_NOT_FOUND


@app.route("/api/v1/add-user", methods=["POST"])
def add_user():
    doc = {
        "first_name": request.json.get("first_name"),
        "last_name": request.json.get("last_name"),
        "username": request.json.get("username"),
        "email": request.json.get("email"),
        "password": flask_bcrypt.generate_password_hash(
            request.json.get("password")
        ).decode(),
    }
    if mongo.db.users.find_one({"email": doc["email"]}) is not None:
        return (
            {"success": False, "already": "both"}
            if mongo.db.users.find_one(
                {"username": doc["username"], "email": doc["email"]}
            )
            is not None
            else {"success": False, "already": "email"}
        )

    if mongo.db.users.find_one({"username": doc["username"]}) is not None:
        return {"success": False, "already": "username"}
    mongo.db.users.insert_one(doc)
    return {"success": True, "already": None}


@app.route("/api/v1/add-comment", methods=["POST"])
def add_comment():
    blog = request.json["blog_title"]
    comment_type = request.json["type"]
    comment_content = f"&zwnj;{request.json['comment_content']}"
    blog_found = mongo.db.blogs.find_one({"title": blog})
    if blog_found is None:
        return {"worked": False}

    if comment_type == "main":
        _id = str(
            mongo.db.comments.insert_one(
                {"comment": comment_content, "user": request.json["user"]}
            ).inserted_id
        )
        comments_tmp = blog_found["comments"]
        comments_tmp.append([_id, []])
    else:
        id_of_comment = request.json["id"]
        if all(comment[0] != id_of_comment for comment in blog_found["comments"]):
            return {"worked": False}
        _id = str(
            mongo.db.comments.insert_one(
                {"comment": comment_content, "user": request.json["user"]}
            ).inserted_id
        )
        comments_tmp = blog_found["comments"]
        for index, comment in enumerate(comments_tmp):
            if comment[0] == request.json["id"]:
                comments_tmp[index][1].append(_id)
                break
    mongo.db.blogs.update_one({"title": blog}, {"$set": {"comments": comments_tmp}})
    return {"worked": True}


@app.route("/api/v1/blog-comments/<blog_title>")
def get_comments(blog_title):
    blog = mongo.db.blogs.find_one({"title": blog_title})
    if blog is None:
        return {"found": False}, status.RESOURCE_NOT_FOUND
    comments = blog["comments"]
    comment_tree = []
    for comment in comments:
        comment_data = mongo.db.comments.find_one({"_id": ObjectId(str(comment[0]))})
        all_comments = {
            "text": comment_data["comment"],
            "user": comment_data["user"],
            "id": str(comment_data["_id"]),
            "sub_comments": [],
        }
        for sub_comment in comment[1]:
            sub_comment_data = mongo.db.comments.find_one(
                {"_id": ObjectId(str(sub_comment))}
            )
            all_comments["sub_comments"].append(
                {
                    "text": sub_comment_data["comment"],
                    "user": sub_comment_data["user"],
                    "id": str(sub_comment),
                }
            )
        comment_tree.append(all_comments)
    return jsonify(comment_tree)


@app.errorhandler(HTTPException)
def error_handling(error):
    flash("Page Not Found")
    return render_template(
        "error.html",
        error=error,
        code=error.code,
        login_status=session["logged_in"] if logged_in(session) else None,
    )


@app.context_processor
def get_blogs():
    def find_blogs():
        return reversed(
            sorted(
                list(mongo.db.blogs.find()),
                key=lambda date: datetime.datetime.strptime(
                    date["date_released"] + date["time_released"],
                    "%m/%d/20%y%H:%M:%S:%f",
                ),
            )
        )

    return dict(find_blogs=find_blogs)


@app.context_processor
def convert_string_to_json():
    def str_to_json(text):
        return {"text": text}

    return dict(str_to_json=str_to_json)


if __name__ == "__main__":
    app.run(debug=True)

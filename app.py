import datetime
import base64
from urllib.parse import quote
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
from bson.objectid import ObjectId
from flask_compress import Compress
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from werkzeug.exceptions import HTTPException
from itsdangerous import URLSafeTimedSerializer

from dotenv import load_dotenv
import pyimgur
import requests

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
    RECAPTCHA_SITEKEY=os.environ["RECAPTCHA_SITEKEY"],
    RECAPTCHA_SECRETKEY=os.environ["RECAPTCHA_SECRETKEY"],
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
        login_status=session["logged_in"] if logged_in(session) else None,
    )


@app.route("/myblogs")
def myblogs():
    if logged_in(session):
        return render_template(
            "myblogs.html",
            login_status=session["logged_in"] if logged_in(session) else None,
        )
    flash(
        Markup(
            'Please <a style="text-decoration: underline;" href="/login">Login</a> or <a style="text-decoration: underline;" href="/sign_up">Sign Up</a> to View Your Blogs'
        )
    )
    return redirect("/")


@app.route("/delete/<title>")
def delete_blog(title):
    if logged_in(session):
        if (
            mongo.db.blogs.find_one(
                {"title": title, "user": session["logged_in"]["username"]}
            )
            is not None
        ):
            mongo.db.blogs.delete_one(
                {"title": title, "user": session["logged_in"]["username"]}
            )
            flash("Blog Has Been Deleted")
        else:
            flash("Blog Not Found")
    else:
        flash(
            Markup(
                'Please <a style="text-decoration: underline;" href="/login">Login</a> or <a style="text-decoration: underline;" href="/sign_up">Sign Up</a> to Delete Your Blogs'
            )
        )
        return redirect("/")
    return redirect("/myblogs")


@app.route("/edit/<title>", methods=["GET", "POST"])
def edit_blog(title):
    if logged_in(session):
        if request.method == "GET":
            blog = mongo.db.blogs.find_one(
                {"title": title, "user": session["logged_in"]["username"]}
            )
            if blog is None:
                flash("Blog Not Found")
                return redirect("/myblogs")
            return render_template(
                "edit.html",
                blog_title=title,
                blog_content=blog["text"],
                login_status=session["logged_in"] if logged_in(session) else None,
                RECAPTCHA_SITEKEY=app.config["RECAPTCHA_SITEKEY"]
            )
        elif request.method == "POST":
            if (
                mongo.db.blogs.find_one(
                    {"title": title, "user": session["logged_in"]["username"]}
                )
                is not None
            ):
                mongo.db.blogs.update_one(
                    {"title": title, "user": session["logged_in"]["username"]},
                    {"$set": {"text": request.form["blog_content"]}},
                )
                flash("Blog Has Been Updated")
            else:
                flash("Blog Not Found")
            return redirect("/myblogs")
    else:
        flash(
            Markup(
                'Please <a style="text-decoration: underline;" href="/login">Login</a> or <a style="text-decoration: underline;" href="/sign_up">Sign Up</a> to Delete Your Blogs'
            )
        )
        return redirect("/")


@app.route("/post_blog")
def post_blog():
    if logged_in(session):
        return render_template(
            "post_blog.html",
            login_status=session["logged_in"] if logged_in(session) else None,
            RECAPTCHA_SITEKEY=app.config["RECAPTCHA_SITEKEY"],
        )
    flash(
        Markup(
            'Please <a style="text-decoration: underline;" href="/login">Login</a> or <a style="text-decoration: underline;" href="/sign_up">Sign Up</a> to Post a Blog'
        )
    )
    return redirect("/")


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if logged_in(session):
        flash("Already Logged In")
        return render_template("/")
    if request.method == "GET":
        return render_template(
            "forgot_password.html",
            login_status=session["logged_in"] if logged_in(session) else None,
        )
    elif request.method == "POST":
        email = request.form.get("email")
        user = mongo.db.users.find_one({"email": email})
        if user is None:
            flash("Email not found")
            return redirect("/forgot_password")
        token = email_url_generator.dumps(user["password"], "change-password")
        confirm_link = url_for("change_password", token=token, _external=True)
        email_oauth.send_message(
            email_oauth_credentials,
            email_oauth.create_message(
                "Blogger101 <blogger101.bot@gmail.com>",
                email,
                "Blogger101 Password Change Confirmation",
                f"Go to {confirm_link} to change your password",
                f"<a href='{confirm_link}'>Change Password<a>",
            ),
        )

        return redirect("/change_password_email_sent")


@app.route("/change_password_email_sent/<token>")
def change_password_email_sent(token):
    email = email_url_generator.loads(token, salt="email-confirm", max_age=3600)
    return render_template(
        "change_password_email_sent.html",
        login_status=session["logged_in"] if logged_in(session) else None,
        email=email,
    )


@app.route("/change_password/<token>", methods=["GET", "POST"])
def change_password(token):
    if request.method == "GET":
        return render_template(
            "change_password.html",
            login_status=session["logged_in"] if logged_in(session) else None,
        )
    elif request.method == "POST":
        password_hash = email_url_generator.loads(
            token, salt="change-password", max_age=3600
        )
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        if password != confirm_password:
            flash("Password Does Not Match Confirm Password")
            return redirect(request.url)
        mongo.db.users.update_one(
            {"password": password_hash},
            {
                "$set": {
                    "password": flask_bcrypt.generate_password_hash(password).decode(),
                }
            },
        )
        flash("Your Password Has Been Updated")
        return redirect("/")


@app.route("/blog/<page>/")
def blog_page(page):
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
def user_page(user):
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
        return render_template(
            "sign_up.html",
            login_status=None,
            RECAPTCHA_SITEKEY=app.config["RECAPTCHA_SITEKEY"],
        )
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

            if (
                mongo.db.users.find_one(
                    {"email": doc["email"], "username": doc["username"]}
                )
                is None
            ):
                token = email_url_generator.dumps(doc["email"], "email-confirm")
                confirm_link = url_for("confirm_email", token=token, _external=True)
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
                if mongo.db.users.find_one({"email": doc["email"]}) is not None:
                    flash("An Account is Already Registered with that Email")
                else:
                    flash("An Account is Already Registered with that Username")
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


@app.route("/confirm_login/<token>")
def confirm_login(token):
    email = email_url_generator.loads(token, salt="email-confirm", max_age=3600)
    user = mongo.db.users.find_one({"email": email})
    if user is not None:
        session["logged_in"] = {
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "email": user["email"],
            "username": user["username"],
        }

        flash("Successfully Logged Up")
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
        return render_template(
            "login.html",
            login_status=None,
            RECAPTCHA_SITEKEY=app.config["RECAPTCHA_SITEKEY"],
        )
    elif request.method == "POST":
        doc = {
            "email": request.form.get("email").lower(),
            "password": request.form.get("password"),
        }
        recaptcha_response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            params={
                "secret": os.environ["RECAPTCHA_SECRETKEY"],
                "response": request.form.get("token"),
            },
        ).json()
        found = mongo.db.users.find_one({"email": doc["email"]})
        if flask_bcrypt.check_password_hash(found["password"], doc["password"]):
            if recaptcha_response["score"] < 0.5:
                token = email_url_generator.dumps(doc["email"], "email-confirm")
                confirm_link = url_for("confirm_login", token=token, _external=True)
                email_oauth.send_message(
                    email_oauth_credentials,
                    email_oauth.create_message(
                        "Blogger101 <blogger101.bot@gmail.com>",
                        doc["email"],
                        "Blogger101 Login Confirmation",
                        f"Go to {confirm_link} to login to your account",
                        f"<a href='{confirm_link}'>Login to Your Account<a>",
                    ),
                )
                return render_template("verify_login.html")
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
    relative = request.args.get("relative", False)
    to_return = []
    for blog in sorted(
        list(mongo.db.blogs.find({})),
        key=lambda date: datetime.datetime.strptime(
            date["date_released"] + date["time_released"], "%m/%d/20%y%H:%M:%S:%f"
        ),
        reverse=True,
    ):
        blog["_id"] = str(blog["_id"])
        if not relative:
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
    return dict(str_to_json=lambda text: {"text": text})


if __name__ == "__main__":
    app.run(debug=True)

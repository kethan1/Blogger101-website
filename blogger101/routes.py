import datetime
import base64
import urllib.parse
import os

from flask import (
    Blueprint,
    current_app,
    render_template,
    redirect,
    flash,
    abort,
    request,
    Markup,
    session,
    jsonify,
    url_for,
    send_from_directory,
)
from bson.objectid import ObjectId
from werkzeug.exceptions import HTTPException
import requests

from blogger101 import http_response_codes as status
from blogger101 import email_oauth
from blogger101 import auth
from blogger101.app_extensions import (
    mongo,
    flask_bcrypt,
    serializer,
)


bp = Blueprint("routes", __name__)


@bp.before_request
def before_request():
    if "DYNO" in os.environ and request.url.startswith("http://"):
        url = request.url.replace("http://", "https://", 1)
        return redirect(urllib.parse.quote(url), code=301)


@bp.route("/.well-known/assetlinks.json")
def send_android_app_link_file():
    return send_from_directory("static", "assetlinks.json")


@bp.route("/")
def blogs():
    return render_template(
        "blogs.html",
        login_status=session["logged_in"] if auth.logged_in(session) else None,
    )


@bp.route("/myblogs")
def myblogs():
    if auth.logged_in(session):
        return render_template(
            "myblogs.html",
            login_status=session["logged_in"] if auth.logged_in(session) else None,
        )
    flash(
        Markup(
            'Please <a style="text-decoration: underline;" href="/login">Login</a> or <a style="text-decoration: underline;" href="/sign_up">Sign Up</a> to View Your Blogs'
        )
    )
    return redirect("/")


@bp.route("/delete/<title>")
def delete_blog(title):
    if auth.logged_in(session):
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


@bp.route("/edit/<title>", methods=["GET", "POST"])
def edit_blog(title):
    if auth.logged_in(session):
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
                login_status=session["logged_in"] if auth.logged_in(session) else None,
                RECAPTCHA_SITEKEY=current_app.config["RECAPTCHA_SITEKEY"],
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


@bp.route("/post_blog")
def post_blog():
    if auth.logged_in(session):
        return render_template(
            "post_blog.html",
            login_status=session["logged_in"] if auth.logged_in(session) else None,
            RECAPTCHA_SITEKEY=current_app.config["RECAPTCHA_SITEKEY"],
        )
    flash(
        Markup(
            'Please <a style="text-decoration: underline;" href="/login">Login</a> or <a style="text-decoration: underline;" href="/sign_up">Sign Up</a> to Post a Blog'
        )
    )
    return redirect("/")


@bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if auth.logged_in(session):
        flash("Already Logged In")
        return render_template("/")
    if request.method == "GET":
        return render_template(
            "forgot_password.html",
            login_status=session["logged_in"] if auth.logged_in(session) else None,
        )
    elif request.method == "POST":
        email = request.form.get("email")
        user = mongo.db.users.find_one({"email": email})
        if user is None:
            flash("Email not found")
            return redirect("/forgot_password")
        token = serializer.dumps(user["password"], "change-password")
        confirm_link = url_for("change_password", token=token, _external=True)
        email_oauth.send_message(
            current_app.config["GMAIL_API_Creds"],
            email_oauth.create_message(
                f"Blogger101 <{current_app.config['EMAIL_SENDER']}>",
                email,
                "Blogger101 Password Change Confirmation",
                f"Go to {confirm_link} to change your password",
                f"<a href='{confirm_link}'>Change Password<a>",
            ),
        )

        return redirect(f"/change_password_email_sent/{token}")


@bp.route("/change_password_email_sent/<token>")
def change_password_email_sent(token):
    email = serializer.loads(token, salt="email-confirm", max_age=3600)
    return render_template(
        "change_password_email_sent.html",
        login_status=session["logged_in"] if auth.logged_in(session) else None,
        email=email,
    )


@bp.route("/change_password/<token>", methods=["GET", "POST"])
def change_password(token):
    if request.method == "GET":
        return render_template(
            "change_password.html",
            login_status=session["logged_in"] if auth.logged_in(session) else None,
        )
    elif request.method == "POST":
        password_hash = serializer.loads(token, salt="change-password", max_age=3600)
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


@bp.route("/blog/<page>/")
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


@bp.route("/user/<user>/")
def user_page(user):
    results = mongo.db.users.find_one({"username": user})
    if auth.logged_in(session):
        return render_template(
            "user_template.html",
            results_from_user=results,
            login_status=session["logged_in"],
        )
    else:
        return render_template(
            "user_template.html", results_from_user=results, login_status=None
        )


@bp.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    if auth.logged_in(session):
        flash("Already Logged In")
        return redirect("/")
    if request.method == "GET":
        return render_template(
            "sign_up.html",
            login_status=None,
            RECAPTCHA_SITEKEY=current_app.config["RECAPTCHA_SITEKEY"],
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
                token = serializer.dumps(doc["email"], "email-confirm")
                confirm_link = url_for(
                    "routes.confirm_email", token=token, _external=True
                )
                email_oauth.send_message(
                    current_app.config["GMAIL_API_Creds"],
                    email_oauth.create_message(
                        f"Blogger101 <{current_app.config['EMAIL_SENDER']}>",
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


@bp.route("/confirm/<token>")
def confirm_email(token):
    email = serializer.loads(token, salt="email-confirm", max_age=3600)
    unverified_user = mongo.db.unverified_users.find_one({"email": email})
    if unverified_user is not None:
        del unverified_user["_id"]
        mongo.db.unverified_users.delete_one(unverified_user)
        mongo.db.users.insert_one(unverified_user)

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


@bp.route("/confirm_login/<token>")
def confirm_login(token):
    email = serializer.loads(token, salt="email-confirm", max_age=3600)
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


@bp.route("/verify_email/<token>")
def verify_email(token):
    email = serializer.loads(token, salt="email-confirm", max_age=3600)
    return render_template("verify_email.html", login_status=None, email=email)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if auth.logged_in(session):
        flash("Already Logged In")
        return redirect("/")
    if request.method == "GET":
        return render_template(
            "login.html",
            login_status=None,
            RECAPTCHA_SITEKEY=current_app.config["RECAPTCHA_SITEKEY"],
        )
    elif request.method == "POST":
        email = request.form.get("email").lower()
        password = request.form.get("password")
        recaptcha_response = (
            {"score": 1}
            if current_app.config["TESTING"]
            else requests.post(
                "https://www.google.com/recaptcha/api/siteverify",
                params={
                    "secret": current_app.config["RECAPTCHA_SECRETKEY"],
                    "response": request.form.get("token"),
                },
            ).json()
        )

        login_response = auth.check_login(email, password)
        if login_response["error"]:
            flash(login_response["message"])
            return redirect("/login")
        user = login_response["user"]

        if flask_bcrypt.check_password_hash(user["password"], password):
            if recaptcha_response["score"] < 0.5:
                token = serializer.dumps(email, "email-confirm")
                confirm_link = url_for("confirm_login", token=token, _external=True)
                email_oauth.send_message(
                    current_app.config["GMAIL_API_Creds"],
                    email_oauth.create_message(
                        f"Blogger101 <{current_app.config['EMAIL_SENDER']}>",
                        email,
                        "Blogger101 Login Confirmation",
                        f"Go to {confirm_link} to login to your account",
                        f"<a href='{confirm_link}'>Login to Your Account<a>",
                    ),
                )
                return render_template("verify_login.html")
            session["logged_in"] = {
                "first_name": user["first_name"],
                "last_name": user["last_name"],
                "email": user["email"],
                "username": user["username"],
            }
            flash("Successfully Logged In")
            return redirect("/")
        else:
            flash("Incorrect Email or Password")
            return redirect("/login")


@bp.route("/logout")
def logout():
    if auth.logged_in(session):
        session["logged_in"] = None
        flash("Successfully Logged Out")
    else:
        flash("Not Logged In")

    return redirect("/")


@bp.route("/api/v1/blogs")
def api_blogs():
    relative = request.args.get("relative", False)
    output = []
    for blog in sorted(
        list(mongo.db.blogs.find({})),
        key=lambda date: datetime.datetime.strptime(
            date["date_released"] + date["time_released"], "%m/%d/20%y%H:%M:%S:%f"
        ),
        reverse=True,
    ):
        blog["_id"] = str(blog["_id"])
        if not relative:
            blog["link"] = urllib.parse.urljoin(
                "https://blogger-101.herokuapp.com", blog["link"]
            )
        output.append(blog)
    return jsonify(output)


@bp.route("/api/v1/post-blog", methods=["POST"])
def api_post_blog():
    title = request.form.get("title")
    user = request.form.get("user")
    blog_content = request.form.get("blog_content")
    name = title.replace(" ", "_").lower()
    to_upload_image = current_app.config["ImgurObject"]._send_request(
        "https://api.imgur.com/3/image",
        method="POST",
        params={"image": base64.b64encode(request.files["file"].read())},
    )
    doc = {
        "title": title,
        "user": user,
        "name": f"{name}.html",
        "text": blog_content,
        "link": f"/blog/{name}",
        "date_released": datetime.datetime.utcnow().strftime("%m/%d/%Y"),
        "time_released": datetime.datetime.utcnow().strftime("%H:%M:%S:%f"),
        "comments": [],
        "image": to_upload_image["link"],
    }

    mongo.db.blogs.insert_one(doc)
    return redirect("/")


@bp.route("/api/v1/auth/check-user", methods=["POST"])
def check_user():
    email = (request.json["email"]).lower()
    password = request.json["password"]

    login_response = auth.check_login(email, password)
    if login_response["error"]:
        return {
            "found": False,
            "message": login_response["message"],
        }, status.USER_NOT_FOUND if login_response[
            "message"
        ] == "A User With That Email Was Not Found" else status.INCORRECT_PASSWORD
    user = login_response["user"]
    user["_id"] = str(user["_id"])

    return {"found": True, "user": user}


@bp.route("/api/v1/auth/add-user", methods=["POST"])
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
    email_already_exists = mongo.db.users.find_one({"email": doc["email"]}) is not None
    username_already_exists = (
        mongo.db.users.find_one({"username": doc["username"]}) is not None
    )
    if email_already_exists or username_already_exists:
        return {
            "success": False,
            "already": "both"
            if email_already_exists and username_already_exists
            else "email"
            if email_already_exists
            else "username",
        }

    mongo.db.users.insert_one(doc)
    return {"success": True, "already": None}


@bp.route("/api/v2/auth/add-user", methods=["POST"])
def add_user_v2():
    doc = {
        "first_name": request.json.get("first_name"),
        "last_name": request.json.get("last_name"),
        "username": request.json.get("username"),
        "email": request.json.get("email"),
        "password": flask_bcrypt.generate_password_hash(
            request.json.get("password")
        ).decode(),
    }
    mobile_phone_uri = request.json.get("mobile_phone_uri")
    email_already_exists = mongo.db.users.find_one({"email": doc["email"]}) is not None
    username_already_exists = (
        mongo.db.users.find_one({"username": doc["username"]}) is not None
    )
    if email_already_exists or username_already_exists:
        return {
            "success": False,
            "already": "both"
            if email_already_exists and username_already_exists
            else "email"
            if email_already_exists
            else "username",
        }

    mongo.db.unverified_users.insert_one(doc)

    token = serializer.dumps(doc["email"], "email-confirm")
    confirm_link = (
        url_for("routes.confirm_email", token=token, _external=True)
        if mobile_phone_uri is None
        else f"{mobile_phone_uri}/email_verification/{token}"
    )
    print(confirm_link)
    email_oauth.send_message(
        current_app.config["GMAIL_API_Creds"],
        email_oauth.create_message(
            f"Blogger101 <{current_app.config['EMAIL_SENDER']}>",
            doc["email"],
            "Blogger101 Email Confirmation",
            f"Go to {confirm_link} to verify your email",
            f"<a href='{confirm_link}'>Verify Email<a>",
        ),
    )

    return {"success": True, "already": None, "email_verification_link": confirm_link}


@bp.route("/api/v1/add-comment", methods=["POST"])
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


@bp.route("/api/v1/blog-comments/<blog_title>")
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


@bp.errorhandler(HTTPException)
def error_handling(error):
    flash("Page Not Found")
    return render_template(
        "error.html",
        error=error,
        code=error.code,
        login_status=session["logged_in"] if auth.logged_in(session) else None,
    )


@bp.context_processor
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


@bp.context_processor
def convert_string_to_json():
    return dict(str_to_json=lambda text: {"text": text})

import json
import os

from flask import Flask
from dotenv import dotenv_values
import pyimgur

from blogger101 import app_extensions
from blogger101.app_extensions import (
    mongo,
    flask_bcrypt,
    flask_compress,
    flask_cors,
)
from blogger101 import email_oauth
from blogger101.routes import bp


if "DYNO" in os.environ:
    config = {
        "IMGUR_ID": os.environ["IMGUR_ID"],
        "MONGO_URI": os.environ["MONGO_URI"],
        "SECRET_KEY": os.environ["SECRET_KEY"],
        "RECAPTCHA_SITEKEY": os.environ["RECAPTCHA_SITEKEY"],
        "RECAPTCHA_SECRETKEY": os.environ["RECAPTCHA_SECRETKEY"],
        "EMAIL_SENDER": os.environ["EMAIL_ADDRESS"],
        "EMAIL_TOKEN": os.environ["EMAIL_TOKEN"],
    }
else:
    config = dotenv_values()
config["EMAIL_TOKEN"] = json.loads(config["EMAIL_TOKEN"])
config["TESTING"] = False

app_extensions.RECAPTCHA_SITEKEY = config["RECAPTCHA_SITEKEY"]


def create_app(test_config=None):
    global app

    app = Flask(__name__)

    config.update({} if test_config is None else test_config)

    app.config.from_mapping(**config)

    mongo.init_app(app)
    flask_bcrypt.init_app(app)
    flask_compress.init_app(app)
    flask_cors.init_app(app)

    app.config["ImgurObject"] = pyimgur.Imgur(app.config["IMGUR_ID"])

    app_extensions.Serialize_Secret_Keys[0] = app.config["SECRET_KEY"]

    app.config["GMAIL_API_Creds"] = email_oauth.load_credentials_from_dict(
        app.config["EMAIL_TOKEN"]
    )

    app.register_blueprint(bp)

    return app

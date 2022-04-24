import os
import sys
import datetime
import pytest
from dotenv import dotenv_values

parent_dir = os.path.abspath(os.path.join(__file__, "../../"))
sys.path.append(parent_dir)

from blogger101 import create_app, app_extensions


@pytest.fixture()
def app():
    app = create_app()
    app.config.update({"TESTING": True, "MONGO_URI": dotenv_values()["MONGO_URI"]})

    app_extensions.mongo.init_app(app)

    app_extensions.mongo.db.users.insert_one(
        {
            "first_name": "Joe",
            "last_name": "Smoe",
            "username": "JoeSmoe",
            "email": "joe@smoe.com",
            "password": app_extensions.flask_bcrypt.generate_password_hash(
                "Password123"
            ).decode(),
        }
    )
    app_extensions.mongo.db.blogs.insert_one(
        {
            "title": "Test Blog",
            "user": "JoeSmoe",
            "name": "Test_Blog.html",
            "text": "`hi` and **bye**",
            "link": "/blog/test_blog",
            "date_released": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%m/%d/%Y"
            ),
            "time_released": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%H:%M:%S:%f"
            ),
            "comments": [],
            "image": "",
        },
    )

    with app.app_context():
        yield app

    app_extensions.mongo.db.users.delete_many({})
    app_extensions.mongo.db.unverified_users.delete_many({})
    app_extensions.mongo.db.blogs.delete_many({})
    app_extensions.mongo.db.comments.delete_many({})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()

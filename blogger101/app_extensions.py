from flask_pymongo import PyMongo
from flask_compress import Compress
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from itsdangerous import URLSafeTimedSerializer

mongo = PyMongo()
flask_bcrypt = Bcrypt()
flask_compress = Compress()
flask_cors = CORS(resources={"/api/*": {"origins": "*"}})

RECAPTCHA_SITEKEY = None
ImgurObject = None

Serialize_Secret_Keys = [""]
serializer = URLSafeTimedSerializer(Serialize_Secret_Keys)

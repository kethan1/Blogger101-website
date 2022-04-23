# Blogger101

This is a simple blogging website similar to Medium. 

## Prerequisites
* Python 3.6 or later
* Pip

## Instructions

You may need to use `python3` and `pip3` instead of `python` and `pip` depending on your installation of Python. 

Clone this repo and then run `pip install -r requirements.txt` to install the needed packages. After that, create an `.env` file in the `blogger101` in the following format:

```
IMGUR_ID=<Imgur ID API Key Here>
MONGO_URI=<MongoDB Atlas (free tier will do) URL. Create a database, and create the collections blogs, comments, and users. Get the url used to access the collection and paste it here.>
SECRET_KEY=<A bunch of random letters used for encrypting the cookies. Something like "test123" will do for development, but make sure to use something longer and more complicated for production>
RECAPTCHA_SITEKEY=<Your site key here>
RECAPTCHA_SECRET=<Your secret key here>
EMAIL_ADDRESS=<The email address to send the emails from>
EMAIL_TOKEN=<The OAuth2 token from the gmail API. The token needs the scope of gmail.send>
```

Then run `python run.py`. The website will be accessible on http://127.0.0.1:5000. 

When deploying to Heroku, you do not need the `.env` file. Instead, add the `Imgur ID`, `MongoDB Connection URL`, `Secret Key`, `reCAPTCHA Sitekey`, `reCAPTCHA Secret`, `Email Address`, and `EMAIL Token` in the Heroku Config Vars, as `IMGUR_ID`, `MONGO_URI`, `SECRET_KEY`, `RECAPTCHA_SITEKEY`, `RECAPTCHA_SECRET`, `EMAIL_ADDRESS`, and `EMAIL_TOKEN`. 

# Blogger101

This is a simple blogging website like Medium. 

## Prerequisites
* Python 3.5 or later installed
* Pip installed

## Instructions

You may need to use `python3` and `pip3` instead of `python` and `pip` depending on your install. 

Download this repo and unzip the folder. Then, `cd` into the folder, and run `pip install -r requirements.txt` to install the needed packages. After that, create an `.env` file with the following format:

```
Imgur_ID=<Imgur ID API Key Here>
MONGO_URI=<MongoDB Atlas (free tier will do) URL. Create a project, and collection with blogs, comments, and users. Get the url for the collection and paste it here.>
SECRET_KEY=<A bunch of random letters used for encrypting the cookies. Something like "test123" will do for development, but make sure to use something longer and more complicated for production>
```

Then run `python app.py`. The website will be accessible on http://127.0.0.1:5000. 

When deploying to Heroku, you do not need the `.env` file. Instead, put the `Imgur ID`, `MongoDB Connection URL`, and `Secret Key` in Heroku Config Vars, as `IMGUR_ID`, `MONGO_URI`, and `SECRET_KEY`. 

from flask import current_app, g
from pymongo import MongoClient


def get_mongo_client():
    """
    Returns a shared MongoClient stored in Flask's `g` context.
    """
    if "mongo_client" not in g:
        uri = current_app.config["MONGODB_URI"]
        g.mongo_client = MongoClient(uri)
    return g.mongo_client


def get_mongo_db():
    """
    Returns the main MongoDB database for this app.
    """
    client = get_mongo_client()
    db_name = current_app.config["MONGODB_DB_NAME"]
    return client[db_name]

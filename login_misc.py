# coding: utf-8

from functools import wraps
from flask import session, request, redirect, flash, url_for, json
from barcamp import app
from hashlib import md5

KEYS = {
    'account': 'account_%s',
    'email': 'email_%s',
    'twitter': 'twitter_%s',
}


def auth_required(fn):
    @wraps(fn)
    def wrap(*args, **kwargs):
        if not session.get('user_hash', False):
            path = request.path
            flash(
                u"Stránka [%s] je dostupná jen přihlášenému uživateli" % path,
                "warning")
            session['next'] = path
            return redirect(url_for('login'))
        return fn(*args, **kwargs)

    return wrap


def check_auth():
    user_hash = session.get('user_hash', None)
    return get_account(user_hash)


def get_account(user_hash):
    return json.loads(app.redis.get(KEYS['account'] % user_hash) or "false")


def create_update_profile(data, user_hash=None):
    if not user_hash:
        user_hash = get_user_hash(data)
        data['user_hash'] = user_hash
    else:
        new_data = get_account(user_hash)
        new_data.update(data)
        data = new_data

    app.redis.set(KEYS['account'] % user_hash, json.dumps(data))
    return user_hash


def get_user_hash(data, depth=5):
    "Non-colide user hash algoritm ;)"
    user_hash = md5("%s|%s" % (json.dumps(data), depth)).hexdigest()[:8]
    if not app.redis.setnx(KEYS['account'] % user_hash, 'false'):
        return get_user_hash(data, depth - 1)

    return user_hash


def update_password(user_hash, email, password=None):
    email = email.lower()
    if password is not None:
        password = md5(password).hexdigest()
    app.redis.set(
        KEYS['email'] % email,
        json.dumps({
            'user_hash': user_hash,
            'password': password
        }))


def resolve_user_by_email(email, password=None):
    """
        Return user ID from email address
        also validates password, if provided
    """
    email = email.lower()
    data = json.loads(app.redis.get(KEYS['email'] % email) or "false")
    if data:
        #check password
        if password and\
                md5(password).hexdigest() != data.get('password', None):
            return False  # password did not match
        return data['user_hash']  # only if everything is OK
    return False  # email not found


def resolve_user_by_twitter(twitter_id):
    return app.redis.get(KEYS['twitter'] % twitter_id) or False


def register_twitter(twitter_id, user_hash):
    return app.redis.set(KEYS['twitter'] % twitter_id, user_hash)


def create_account(email, password, user_hash=None, data=None):
    data = data or {}

    data.update({'email': email, 'password': password})
    email = email.lower()
    user_hash = create_update_profile(data)
    update_password(user_hash, email, password)

    return user_hash

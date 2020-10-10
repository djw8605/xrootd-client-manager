# -*- coding: utf-8 -*-

"""
Chat Server
===========

This simple application uses WebSockets to run a primitive chat server.
"""

import os
import redis
from flask import Flask, render_template, request, session, url_for, redirect, flash, abort
from flask_socketio import SocketIO, disconnect, send
import logging
import json
import uuid
from flask_dance.contrib.github import make_github_blueprint, github

REDIS_URL = os.environ['REDIS_URL']
REDIS_CHAN = 'chat'
XROOTD_CLIENT = 'xrootd-clients'

app = Flask(__name__)
app.debug = 'DEBUG' in os.environ
app.secret_key = os.environ['SESSION_KEY']

socketio = SocketIO(app)
redis = redis.from_url(REDIS_URL)

app.config["GITHUB_OAUTH_CLIENT_ID"] = os.environ.get("GITHUB_OAUTH_CLIENT_ID")
app.config["GITHUB_OAUTH_CLIENT_SECRET"] = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET")
github_bp = make_github_blueprint()
app.register_blueprint(github_bp, url_prefix="/login")


class ChatBackend(object):
    """Interface for registering and updating WebSocket clients."""

    def __init__(self):
        self.clients = {}
        self.pubsub = redis.pubsub()
        self.pubsub.subscribe(REDIS_CHAN)

    def __iter_data(self):
        for message in self.pubsub.listen():
            data = message.get('data')
            if message['type'] == 'message':
                app.logger.info(u'Sending message: {}'.format(data))
                yield data

    def add_worker(self, client_id):
        """Register a WebSocket connection for Redis updates."""
        # Check if we have already registered this client
        if not redis.get(client_id):
            return False
        redis.persist(client_id)
        redis.sadd(XROOTD_CLIENT, client_id)
        self.clients[client_id] = 1
        return True
    
    def register_worker(self, client_id, client_details):

        redis.setex(client_id, 30, json.dumps(client_details))
        
    def remove(self, client_id):
        """
        Remove the id
        """
        app.logger.debug("Removing client: {}".format(client_id))
        redis.srem(XROOTD_CLIENT, client_id)
        redis.expire(client_id, 30)
        del self.clients[client_id]
    
    def get_workers(self):
        """
        Return all workers and details about them
        """
        # Get all client ids
        client_ids = redis.smembers(XROOTD_CLIENT)
        clients = {}
        for client_id in client_ids:
            client = redis.get(client_id)
            if client is not None:
                clients[client_id.decode('utf-8')] = json.loads(client)
        return clients

    def get_num_workers(self):
        """
        Return a single integer on the number of connected workers
        """
        return redis.scard(XROOTD_CLIENT)

    def run(self):
        """Listens for new messages in Redis, and sends them to clients."""
        for data in self.__iter_data():
            socketio.emit('command', data)

    def start(self):
        """Maintains Redis subscription in the background."""
        socketio.start_background_task(self.run)

chats = ChatBackend()
chats.start()

#@app.route('/login')
#def login():
#    if not osg_blueprint.authorized:
#        return redirect(url_for("google.login"))
#    resp = google.get("/userinfo")
#    assert resp.ok, resp.text
#    return "You are {email} on Google".format(email=resp.json()["email"])

def authorized(func):
    def wrapper(*args, **kwargs):
        if 'Authorization' in request.headers and request.headers['Authorization'] == "Bearer xyz":
            token_authorized = True
        if not github.authorized and not token_authorized:
            abort(401)
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@app.route('/')
def index():
    if not github.authorized:
        return redirect(url_for("github.login"))
    if 'github_id' not in session:
        resp = github.get("/user")
        assert resp.ok
        login=resp.json()["login"]
        session['github_id'] = login
    return render_template('index.html', login=session['github_id'])

@app.route('/getclients')
@authorized
def get_clients():
    # The user must be github authorized, or have a bearer token

    workers = chats.get_workers()
    return json.dumps(workers)

@app.route('/getnumclients')
def get_num_clients():
    return str(chats.get_num_workers())


@app.route('/send-command', methods=['POST'])
@authorized
def send_command():
    command = {
        'command': 'ping'
    }
    app.logger.info(u'Inserting message: {}'.format(json.dumps(command)))
    redis.publish(REDIS_CHAN, json.dumps(command))
    return "", 200

@socketio.on('connect')
def listen():
    """Sends outgoing chat messages, via `ChatBackend`."""

    app.logger.info("Connection received")
    # Save the uuid from the client
    if 'id' not in request.args:
        disconnect()
        return "No id in request", 400
    
    client_id = request.args['id']
    session['client_id'] = client_id
    register_worked = chats.add_worker(client_id)
    if not register_worked:
        disconnect()
        return "Client not registered", 400

@socketio.on('disconnect')
def on_disconnect():
    client_id = session['client_id']
    app.logger.debug("Client disconnected: {}".format(client_id))
    chats.remove(client_id)

@app.route('/register', methods=['POST'])
def register():
    """
    Register a client and get an ID
    """
    if 'Authorization' not in request.headers:
        return "Not authorized", 401

    # Check the authorization bearer token

    # Add the client to the chat
    client_details = request.json
    # Generate a uuid for the client and return it
    client_id = str(uuid.uuid4())
    chats.register_worker(client_id, client_details)
    to_return = {
        'client_id': client_id
    }
    return json.dumps(to_return)



if __name__ == "__main__":
    print("In main")
    chats.start()
    socketio.run(app)
    print("after socktio.run")



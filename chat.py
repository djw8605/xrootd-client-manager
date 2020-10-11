# -*- coding: utf-8 -*-

"""
Chat Server
===========

This simple application uses WebSockets to run a primitive chat server.
"""

import os
import redis
from flask import Flask, render_template, request, session, url_for, redirect, flash, abort
from flask_socketio import SocketIO, disconnect, send, join_room, leave_room, emit
import logging
import json
import uuid
from flask_dance.contrib.github import make_github_blueprint, github
import hashlib

REDIS_URL = os.environ['REDIS_URL']
REDIS_CHAN = 'chat'
XROOTD_CLIENT = 'xrootd-clients'
XROOTD_SERVER = 'xrootd-server'

app = Flask(__name__)
app.debug = 'DEBUG' in os.environ
app.secret_key = os.environ['SESSION_KEY']

socketio = SocketIO(app, redis=REDIS_URL)
redis = redis.from_url(REDIS_URL)

app.config["GITHUB_OAUTH_CLIENT_ID"] = os.environ.get("GITHUB_OAUTH_CLIENT_ID")
app.config["GITHUB_OAUTH_CLIENT_SECRET"] = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET")
github_bp = make_github_blueprint()
app.register_blueprint(github_bp, url_prefix="/login")


class ChatBackend(object):
    """Interface for registering and updating WebSocket clients."""

    def __init__(self):
        self.clients = {}
        self.servers = {}

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

        redis_return = redis.setex(client_id, 30, json.dumps(client_details))
        app.logger.debug("Redis registration return: {}".format(str(redis_return)))
    
    def register_server(self, server_id, server_details):
        redis_return = redis.setex(server_id, 30, json.dumps(server_details))
        app.logger.debug("Redis registration return: {}".format(str(redis_return)))

    def add_server(self, server_id):
        """Register a WebSocket connection for Redis updates."""
        # Check if we have already registered this client
        if not redis.get(server_id):
            return False
        redis.persist(server_id)
        redis.sadd(XROOTD_SERVER, server_id)
        self.servers[server_id] = 1
        return True
    
    def remove_server(self, server_id):
        """
        Remove the id
        """
        app.logger.debug("Removing server: {}".format(server_id))
        redis.srem(XROOTD_SERVER, server_id)
        redis.expire(server_id, 30)
        del self.servers[server_id]
        
    def remove_worker(self, client_id):
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
    
    def get_servers(self):
        """
        Return all workers and details about them
        """
        # Get all client ids
        server_ids = redis.smembers(XROOTD_SERVER)
        servers = {}
        for server_id in server_ids:
            server = redis.get(server_id)
            if server is not None:
                servers[server_id.decode('utf-8')] = json.loads(server)
        return servers
    
    def get_worker_details(self, client_id):
        """
        Return a single worker's details
        """
        return redis.get(client_id)
        

    def get_num_workers(self):
        """
        Return a single integer on the number of connected workers
        """
        return redis.scard(XROOTD_CLIENT)



chats = ChatBackend()

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
        return render_template('index.html', authenticated=False)

    if 'github_id' not in session:
        resp = github.get("/user")
        assert resp.ok
        login=resp.json()["login"]
        session['github_id'] = login
    return render_template('index.html', authenticated=True, login=session['github_id'])

@app.route('/getclients')
@authorized
def get_clients():
    # The user must be github authorized, or have a bearer token

    workers = chats.get_workers()
    # Switch the client_id to sha sum of the client_id
    cleaned_workers = {}
    for key, value in workers.items():
        m = hashlib.sha256()
        m.update(key.encode('utf-8'))
        cleaned_key = m.hexdigest()
        cleaned_workers[cleaned_key] = value
    return json.dumps(cleaned_workers)

@app.route('/getservers')
@authorized
def get_servers():
    # The user must be github authorized, or have a bearer token

    servers = chats.get_servers()
    # Switch the client_id to sha sum of the client_id
    cleaned_servers = {}
    for key, value in servers.items():
        m = hashlib.sha256()
        m.update(key.encode('utf-8'))
        cleaned_key = m.hexdigest()
        cleaned_servers[cleaned_key] = value
    return json.dumps(cleaned_servers)

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
    socketio.emit('command', json.dumps(command), room="workers")
    return "", 200

@socketio.on('connect')
def listen():
    """Sends outgoing chat messages, via `ChatBackend`."""
    if 'github_id' in session:
        # If it's github authorized, then it's a web user
        # Send the user to the special web user room
        join_room("web")
        return

    app.logger.info("Connection received")
    # Save the uuid from the client
    if 'id' not in request.args:
        app.logger.error("ID not in socket.io args")
        disconnect()
        return "No id in request", 400
    
    is_server = False
    if 'server' in request.args:
        is_server = True

    client_id = request.args['id']
    session['client_id'] = client_id
    if not is_server and not chats.add_worker(client_id):
        app.logger.info("Worker {} not registered".format(client_id))
        disconnect()
        return "Client not registered", 400
    if is_server and not chats.add_server(client_id):
        app.logger.info("Server {} not registered".format(client_id))
        disconnect()
        return "Server not registered", 400
    
    if is_server:
        join_room("servers")
    else:
        join_room("workers")
    
    m = hashlib.sha256()
    m.update(client_id.encode('utf-8'))
    cleaned_key = m.hexdigest()
    details = {
        'client_id': cleaned_key
    }
    details.update(json.loads(chats.get_worker_details(client_id)))

    if is_server:
        emit('new server', details, room="web")
    else:
        emit('new worker', details, room="web")

@socketio.on('disconnect')
def on_disconnect():
    if 'client_id' in session:
        is_server = False
        if 'server' in request.args:
            is_server = True
        client_id = session['client_id']
        app.logger.debug("Client disconnected: {}".format(client_id))
        if is_server:
            chats.remove_server(client_id)
            emit('server left', client_id, room="web")
        else:
            chats.remove_worker(client_id)
            emit('worker left', client_id, room="web")

@app.route('/register', methods=['POST'])
def register():
    """
    Register a client or server and get an ID
    """
    if 'Authorization' not in request.headers:
        return "Not authorized", 401

    # Check the authorization bearer token

    # Check for the server in the query
    is_server = False
    if 'server' in request.args:
        # This is a server
        is_server = True

    # Add the client to the chat
    client_details = request.json
    # Generate a uuid for the client and return it
    client_id = str(uuid.uuid4())
    if is_server:
        app.logger.debug("Registering new server: {}".format(client_id))
        chats.register_server(client_id, client_details)
    else:
        app.logger.debug("Registering new worker: {}".format(client_id))
        chats.register_worker(client_id, client_details)

    to_return = {
        'client_id': client_id
    }
    return json.dumps(to_return)


if __name__ == "__main__":
    print("In main")
    socketio.run(app)
    print("after socktio.run")



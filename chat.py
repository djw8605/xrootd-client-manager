# -*- coding: utf-8 -*-

"""
Chat Server
===========

This simple application uses WebSockets to run a primitive chat server.
"""

import os
import redis
import gevent
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, disconnect
import logging
import json
import uuid

REDIS_URL = os.environ['REDIS_URL']
REDIS_CHAN = 'chat'
XROOTD_CLIENT = 'xrootd-clients'

app = Flask(__name__)
app.debug = 'DEBUG' in os.environ
app.secret_key = os.environ['SESSION_KEY']

socketio = SocketIO(app)
redis = redis.from_url(REDIS_URL)


class ChatBackend(object):
    """Interface for registering and updating WebSocket clients."""

    def __init__(self):
        self.clients = {}
        self.pubsub = redis.pubsub()
        self.pubsub.subscribe(REDIS_CHAN)
        # When I first start up, flush redis
        redis.flushall()

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
            socketio.send(data)

    def start(self):
        """Maintains Redis subscription in the background."""
        gevent.spawn(self.run)




@app.route('/')
def hello():
    return render_template('index.html')

@app.route('/getclients')
def get_clients():
    workers = chats.get_workers()
    print(workers)
    return workers

@app.route('/getnumclients')
def get_num_clients():
    return str(chats.get_num_workers())


@app.route('/send-command', methods=['POST'])
def send_command():
    command = {
        'command': 'ping'
    }
    app.logger.info(u'Inserting message: {}'.format(json.dumps(command)))
    redis.publish(REDIS_CHAN, json.dumps(command))
    return "", 200

@socketio.on('connect', namespace='/listen')
def listen():
    """Sends outgoing chat messages, via `ChatBackend`."""

    app.logger.info("Connection received")
    logging.info("Connection received")
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
        

@socketio.on('disconnect', namespace='/listen')
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
    return to_return



if __name__ == '__main__':
    chats = ChatBackend()
    chats.start()
    socketio.run(app)



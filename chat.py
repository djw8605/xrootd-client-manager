# -*- coding: utf-8 -*-

"""
Chat Server
===========

This simple application uses WebSockets to run a primitive chat server.
"""

import os
import logging
import redis
import gevent
from flask import Flask, render_template, request   
from flask_sockets import Sockets
import json
import uuid

REDIS_URL = os.environ['REDIS_URL']
REDIS_CHAN = 'chat'
XROOTD_CLIENT = 'xrootd-clients'

app = Flask(__name__)
app.debug = 'DEBUG' in os.environ

sockets = Sockets(app)
redis = redis.from_url(REDIS_URL)


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

    def add_worker(self, client, client_id):
        """Register a WebSocket connection for Redis updates."""
        # Check if we have already registered this client
        if not redis.get(client_id):
            return False
        redis.sadd(XROOTD_CLIENT, client_id)
        self.clients[client_id] = client
        return True
    
    def register_worker(self, client_id, client_details):

        redis.setex(client_id, 30, json.dumps(client_details))


    def send(self, client, data):
        """Send given data to the registered client.
        Automatically discards invalid connections."""
        try:
            client.send(data)
        except Exception:
            self.remove(client)
        
    def remove(self, client_id):
        """
        Remove the id
        """
        redis.srem(XROOTD_CLIENT, client_id)
        redis.delete(client_id)
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
            for client in self.clients:
                gevent.spawn(self.send, client, data)

    def start(self):
        """Maintains Redis subscription in the background."""
        gevent.spawn(self.run)

chats = ChatBackend()
chats.start()


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

@sockets.route('/submit')
def inbox(ws):
    """Receives incoming chat messages, inserts them into Redis."""
    while not ws.closed:
        # Sleep to prevent *constant* context-switches.
        gevent.sleep(0.1)
        message = ws.receive()

        if message:
            app.logger.info(u'Inserting message: {}'.format(message))
            redis.publish(REDIS_CHAN, message)

@sockets.route('/listen')
def listen(ws):
    """Sends outgoing chat messages, via `ChatBackend`."""

    # Save the uuid from the client
    if 'id' not in request.args:
        return "No id in request", 400
    
    client_id = request.args['id']

    register_worked = chats.add_worker(ws, client_id)
    if not register_worked:
        return "Client not registered", 400

    while not ws.closed:
        # Context switch while `ChatBackend.start` is running in the background.
        gevent.sleep(0.1)

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

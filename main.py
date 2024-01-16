import os
import subprocess
import webview
import socketio
from flask import Flask, render_template, send_from_directory
import eventlet
from datetime import datetime
import time
from webview.platforms.cef import browser_settings, settings
import json
from datetime import timedelta
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.services.storage import Storage
from appwrite.id import ID as id_class
from appwrite.input_file import InputFile

# Create a new Socket.IO server
sio = socketio.Server()

# Create a new Flask web application
app = Flask(__name__)

# Attach the Socket.IO server to the Flask application
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)

# Initialize the AppWrite client
client = Client()
client.set_endpoint('https://cloud.appwrite.io/v1')  # Replace with your AppWrite endpoint
client.set_project('privatetable-chat')  # Replace with your AppWrite project ID
client.set_key('44f3e53186bb0eab5e62a152dc8e8ebe88895ec116539d0b43920427417959dc4c8c5ea5d4e446b64f991e7e9e6bdeb87551dadf4fe1d652038c830d440b1b61782ac5ca32b98c765c5f8eff0de5ebeebbbd42c40b58cce1ff4e2af671fc3ffe6f868fcc4f9e579973800f1fd2e76fe1349df0b852ef4610d74f9115807786c0')  # Replace with your AppWrite API key

# Get the Database service
database = Databases(client)

# Get the storage service
storage = Storage(client)

# Add message dict
messages = {}

# This part is to check if any message is older than 90 days, then deletes it.
def delete_old_msgs():
    # Get all documents in the 'chat-msgs-collection' collection
    response = database.list_documents('chat-msgs', 'chat-msgs-collection')

    for document in response['documents']:
        timestamp = datetime.strptime(document['timestamp'], '%d %b, %Y • %I:%M:%S')
        if datetime.now() - timestamp > timedelta(days=90):
            # If the message is older than 90 days, delete it
            database.delete_document('chat-msgs', 'chat-msgs-collection', document['$id'])

# Serve the index.html file for the chat app
@app.route('/')
def index():
    return render_template('index.html')

@app.route("/icon/file.svg")
def preview_file():
    return send_from_directory(os.path.abspath("./templates/icons"), "file.svg")

@app.route('/css')
def css():
    return send_from_directory("./templates/css", "styles.css")


# Define event handlers
@sio.event
def connect(sid, environ):
    print(f"Client {sid} connected")
    send_stored_messages(sid)


@sio.event
def disconnect(sid):
    print(f"Client {sid} disconnected")


@sio.event
def file_upload(sid, file):
   # Upload the file to AppWrite
   if file:
        file = bytearray(str(file), "utf-8");
        print(file)
        filepath = InputFile.from_bytes(file);
        response = storage.create_file("attachments", id_class.unique(), filepath)

        if response['status'] == 201:
           print('File uploaded successfully')

           # Check if the file is an image
           if response['content_type'].startswith('image/'):
               # Get the URL of the file preview
               url = storage.get_file_preview('attachments', response['$id'], width=200)
           else:
               # Use a generic icon for other file types
               url = '/icon/file.svg'

           # Send the URL back to the client
           sio.send(sid, url)
        else:
           print('Failed to upload file')
   else:
       pass

@sio.event
def chat_message(sid, data):
   timestamp = datetime.now().strftime('%d %b, %Y • %I:%M:%S')
   if data == "" or None:
       pass
   else:
       print(data)
       message = {'timestamp': timestamp, 'data': data}
       if 'image_url' in data:
           message['image_url'] = data['image_url']
       messages.setdefault(sid, []).append(message)

       # Store the message in Appwrite
       document = database.create_document('chat-msgs','chat-msgs-collection', id_class.unique(), {'timestamp': timestamp, 'message': data, 'image_url': message.get('image_url')})

       sio.send(sid, "Message received by server: " + data)
       sio.emit('message', json.dumps(message))



def send_stored_messages(sid):
    stored_messages = messages.get(sid, [])
    for message in stored_messages:
        sio.emit('message', json.dumps(message), room=sid)


def run_flask():
    eventlet.wsgi.server(eventlet.listen(('127.0.0.1', 5000)), app)


def startup():
    delete_old_msgs()
    # Start Flask app in a subprocess
    flask_process = subprocess.Popen([os.path.abspath('./p.bat'), 'run_flask'])

    def on_closing():
        # Inform the server that the window is closing
        socketio.emit('window_closing')

        # Allow some time for the server to handle the event
        time.sleep(1)

        # Terminate the Flask process
        flask_process.terminate()

    # Schedule the on_closing function to be called when the webview window is closed
    # Update the settings as needed
    settings.update({'persist_session_cookies': True})
    browser_settings.update({'dom_paste_disabled': False})
    webview.create_window('PrivateTable Chatroom', 'http://localhost:5000')
    webview.start(gui="cef")
    
    



if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'run_flask':
        run_flask()
    else:
        startup()

#!/usr/bin/python3
"""Run a simple http server for the Ajahn Pasanno Archive.
Inteded for local use only; no need to allow this through the firewall."""

import os,sys
import http.server
import threading
import time
import webbrowser

httpPort = 9000
scriptDir,_ = os.path.split(os.path.abspath(sys.argv[0]))
baseDir = os.path.split(scriptDir)[0]
print("Serving from",baseDir,"on port",httpPort)

# Code from https://stackoverflow.com/questions/31251524/python-simplehttpserver-change-service-directory
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=baseDir, **kwargs)

# Define server parameters
server_address = ('', httpPort)
httpd = http.server.HTTPServer(server_address, Handler)

# 1. Run serve_forever() inside a separate background thread
server_thread = threading.Thread(target=httpd.serve_forever)
server_thread.daemon = True
server_thread.start()
print("Server is starting...")

time.sleep(1)
webAddress = f"http://127.0.0.1:{httpPort}/index.html"
print("Opening",webAddress)
webbrowser.open(webAddress)

# Run an event loop to poll for completion
while (True):
    cmd = input("Type 'quit' to quit or 'open' to reopen web page: ")
    if 'quit' in cmd.lower():
        break
    if 'open' in cmd.lower():
        print("Opening",webAddress)
        webbrowser.open(webAddress)

print("Exiting...")

"""
This code to close the server nicely sometimes hangs, so we don't use it

# 2. Stop the server safely from the main thread
print("Stopping server...")
httpd.shutdown()  # Stops the serve_forever loop cleanly

print("Calling server_close...")
httpd.server_close()  # Closes the server socket completely
"""
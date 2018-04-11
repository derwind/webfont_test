#! /usr/bin/env python
# -*- coding: utf-8 -*-

from bottle import route, run, template, static_file
import socket

@route("/")
def index():
    return static("index.html")

@route('/<file_path:path>')
def static(file_path):
    return static_file(file_path, root="./document_root")

if __name__ == "__main__":
    ip_addr = socket.gethostbyname(socket.gethostname())
    run(host=ip_addr, port=8080)

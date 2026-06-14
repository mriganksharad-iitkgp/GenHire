#!/bin/bash
echo "Starting Flask Application with Gunicorn and Eventlet..."
gunicorn -c gunicorn.conf.py app:app

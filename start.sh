#!/bin/bash

if [ ! -d env ]; then
  echo "Creating the virtual environment"
  python3 -mvenv env
fi

. env/bin/activate
pip3 install -r requirements.txt

cd app && uvicorn app:app --host 0.0.0.0 --port 8000 --reload

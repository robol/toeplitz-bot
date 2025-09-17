# HPC Cluster AI Assistant

This is an attempt to an Ollama-based AI Chatbot to assist
users of the HPC Cluster of the Math Department of the 
University of Pisa.

## Ollama
A prerequisite to run the server is to have Ollama up and 
running either on the local machine, or somewhere else. If 
it is hosted somewhere else, make sure to export the 
relevant environment variables:
```bash
export OLLAMA_URL = "http://localhost:11434/api/chat"
export OLLAMA_MODEL = "mistral"
```

## Development
To start the local server on Linux, you may use the ``start.sh``
script provided in the repository. 

## Manual setup of the development environment
To manually setup the environment, run the following commands, 
or their equivalent for your operating system:
```bash
python3 -menv 
. env/bin/activate
pip3 install -r requirements.txt
ollama run mistral
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

## Deploy
To deploy the server, ``gunicorn`` is preferred:
```bash
gunicorn app:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 4
```

# 

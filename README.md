# Job Application Agent

A multi-agent system that helps users **find jobs** and (in future) **improve
applications**. Agents share capabilities and data through a single **MCP
server**, which is the communication backbone for adding more agents later.

## Setup

### Setup python venv

When python is installed on your machine use this command to create a virtual environment:

```bash
python -m venv ./venv
```

Then activate the venv by:

```bash
source ./venv/bin/activate
```

Then install the required packages:

```bash
pip install -r requirements.txt
```

### Setup Environment Variables

Setup env vars by copying the example env vile like this:

```bash
cp .env.example .env
```

Then edit the values in the .env file.

### Setup Ollama

Make sure Ollama is running and the model is pulled:

```bash
ollama serve
ollama pull qwen3.5:4b
```

Ollama needs to be running on port 11434, otherwise it can be adjusted in .env file.

## Run

If you want you can put files (.md) inside the ./ChromaDB/docs folder and then run the following command to insert the files to the RAG DB:

```bash
python -m ingest
```

The agent and the MCP server are separate processes.
The MCP server needs to run by running:

```bash
python -m mcp_server
```

After that the agents can be started by running:

```bash
python -m main
```

## Example

> Ich suche eine Stelle als Softwareentwickler in Berlin, Vollzeit.

The agent searches the Arbeitsagentur job board, caches the offers in the RAG
store, categorizes them and presents a list. If nothing matches it returns an
empty list and suggests relaxing the preferences.

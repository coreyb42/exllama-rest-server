import argparse
import json
import os
import sys
from threading import Timer, Lock
import webbrowser

from flask import Flask, render_template, request
from flask import Response, stream_with_context
from waitress import serve

import model_init
from model import ExLlama
from session import get_generator, get_initial_session, load_session, new_session, prepare_sessions, Session, \
    _sessions_dir
from tokenizer import ExLlamaTokenizer


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app = Flask(__name__)
app.static_folder = 'static'
generate_lock = Lock()
session: Session


@app.route("/")
def home():
    return render_template("index.html")


# Render template
@app.route('/api/infer_precise', methods=['POST'])
def infer_context_p():
    print(request.form)
    prompt = request.form.get('prompt')
    generator = get_generator()

    # Get parameters from request if provided, else use defaults
    token_repetition_penalty_max = float(request.form.get('token_repetition_penalty_max', 1.176))
    token_repetition_penalty_sustain = int(request.form.get('token_repetition_penalty_sustain', config.max_seq_len))
    temperature = float(request.form.get('temperature', 0.7))
    top_p = float(request.form.get('top_p', 0.1))
    top_k = int(request.form.get('top_k', 40))
    typical = float(request.form.get('typical', 0.0))
    max_new_tokens = int(request.form.get('max_new_tokens', 3000))

    generator.settings.token_repetition_penalty_max = token_repetition_penalty_max
    generator.settings.token_repetition_penalty_sustain = token_repetition_penalty_sustain
    generator.settings.temperature = temperature
    generator.settings.top_p = top_p
    generator.settings.top_k = top_k
    generator.settings.typical = typical    # Disabled if 0.0

    outputs = generator.generate_simple(prompt, max_new_tokens=max_new_tokens)
    return outputs


# Get existing sessions
@app.route("/api/populate")
def api_populate():
    global session
    return session.api_populate()


# Edit block
@app.route("/api/edit_block", methods=['POST'])
def api_edit_block():
    global session
    data = request.get_json()
    session.api_edit_block(data)
    return json.dumps({"result": "ok"}) + "\n"


# Delete block
@app.route("/api/delete_block", methods=['POST'])
def api_delete_block():
    global session
    data = request.get_json()
    session.api_delete_block(data)
    return json.dumps({"result": "ok"}) + "\n"


# Rename session
@app.route("/api/rename_session", methods=['POST'])
def api_rename_session():
    global session
    data = request.get_json()
    success = session.api_rename_session(data)
    return json.dumps({"result": "ok" if success else "fail"}) + "\n"


# Delete session
@app.route("/api/delete_session", methods=['POST'])
def api_delete_session():
    global session
    data = request.get_json()
    session.api_delete_session(data)
    return json.dumps({"result": "ok"}) + "\n"


# Set fixed prompt settings
@app.route("/api/set_fixed_prompt", methods=['POST'])
def api_set_fixed_prompt():
    global session
    data = request.get_json()
    session.api_set_fixed_prompt(data)
    return json.dumps({"result": "ok"}) + "\n"


# Set generation settings
@app.route("/api/set_gen_settings", methods=['POST'])
def api_set_gen_settings():
    global session
    data = request.get_json()
    session.api_set_gen_settings(data)
    return json.dumps({"result": "ok"}) + "\n"


# Set session
@app.route("/api/set_session", methods=['POST'])
def api_set_session():
    global session
    data = request.get_json()
    load_session_name = data["session_name"]
    if load_session_name == ".":
        session = new_session()
    else:
        session = load_session(load_session_name, append_path=True)
    return json.dumps({"result": "ok"}) + "\n"


# Set participants
@app.route("/api/set_participants", methods=['POST'])
def api_set_participants():
    global session
    data = request.get_json()
    session.api_set_participants(data)
    return json.dumps({"result": "ok"}) + "\n"


# Accept input
@app.route("/api/userinput", methods=['POST'])
def api_userinput():
    data = request.get_json()
    user_input = data["user_input"]

    with generate_lock:
        result = Response(stream_with_context(session.respond_multi(user_input)), mimetype='application/json')
        return result


@app.route("/api/append_block", methods=['POST'])
def api_append_block():
    data = request.get_json()
    session.api_append_block(data)
    return json.dumps({"result": "ok"}) + "\n"


# Load the model

parser = argparse.ArgumentParser(description="Simple web-based chatbot for ExLlama")
parser.add_argument("-host", "--host", type=str, help="IP:PORT eg, 0.0.0.0:7862", default="localhost:5000")
parser.add_argument("-sd", "--sessions_dir", type=str,
                    help="Location for storing user sessions, default: ~/exllama_sessions/",
                    default="~/exllama_sessions/")

model_init.add_args(parser)
args = parser.parse_args()
model_init.post_parse(args)
model_init.get_model_files(args)

model_init.print_options(args)
config = model_init.make_config(args)

print(f" -- Loading model...")
model = ExLlama(config)

print(f" -- Loading tokenizer...")
tokenizer = ExLlamaTokenizer(args.tokenizer)

model_init.print_stats(model)

# Get the session ready

prepare_sessions(model, tokenizer, args.sessions_dir)
session = get_initial_session()

print(f" -- Sessions stored in: {_sessions_dir()}")

# Start the web server

machine = args.host
host, port = machine.split(":")

if host == "localhost":
    Timer(1, lambda: webbrowser.open(f'http://{machine}/')).start()

serve(app, host=host, port=port)

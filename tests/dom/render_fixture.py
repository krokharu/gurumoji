"""Render trusted templates without importing Gurumoji, opening a DB or a server."""
from pathlib import Path
import sys
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
env = Environment(loader=FileSystemLoader(root / 'src/gurumoji/templates'), undefined=StrictUndefined,
                  autoescape=select_autoescape(['html']))
print(env.get_template('index.html').render(
    app_name='Gurumoji synthetic DOM fixture', app_version='test',
    local_llm_label='Synthetic local LLM', local_llm_short_label='Local',
    runtime=dict(label='synthetic runtime', native_file_dialog=False, colab=False,
                 source_path_example='/synthetic/input.wav', qwen_setup_note='Synthetic'),
    url_for=lambda endpoint, filename: '/static/' + filename))

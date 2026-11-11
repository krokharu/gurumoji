"""公開候補の素材定義で合成画面を描画する。アプリ・DBは読み込まない。"""
from pathlib import Path
import runpy, sys
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
sys.stdout.reconfigure(encoding='utf-8')
root = Path(sys.argv[1]).resolve()
assets = runpy.run_path(str(root / 'src/gurumoji/web/assets.py'))
env = Environment(loader=FileSystemLoader(root / 'src/gurumoji/templates'), undefined=StrictUndefined, autoescape=select_autoescape(['html']))
print(env.get_template('index.html').render(
    app_name='Gurumoji synthetic DOM fixture', app_version='test', obsidian_enabled=False, analysis_enabled=False,
    application_styles=assets['application_styles'](False), application_scripts=assets['application_scripts'](False),
    local_llm_label='Synthetic local LLM', local_llm_short_label='Local',
    runtime=dict(label='synthetic runtime', native_file_dialog=False, colab=False, source_path_example='/synthetic/input.wav', qwen_setup_note='Synthetic', haas_setup_note='Synthetic'),
    url_for=lambda endpoint, filename: '/static/' + filename))
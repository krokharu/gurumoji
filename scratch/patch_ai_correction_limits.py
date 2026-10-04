from pathlib import Path
p=Path('scratch/run_ai_correction_comparison.py')
s=p.read_text(encoding='utf-8-sig')
s=s.replace('for char_limit,item_limit in ((10000,160),(3000,32),(1800,16),(900,8)):', 'for char_limit,item_limit in ((3000,32),(1800,16),(900,8)):')
s=s.replace("if '発話ID' not in str(exc): raise", "if not any(marker in str(exc) for marker in ('発話ID','HTTP 400','入力の長さ','有効な JSON')): raise")
p.write_text(s,encoding='utf-8')

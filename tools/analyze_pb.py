from pathlib import Path
import subprocess

D = Path('/home/ubuntu/gboard_patch/orig/assets/theme')
for name in ['style_sheet_default.binarypb','style_sheet_default_light.binarypb','style_sheet_color_common.binarypb','style_sheet_color_rules.binarypb','style_sheet_dynamic_color_rules.binarypb','style_sheet_material3_light.binarypb']:
    p = D / name
    if not p.exists():
        continue
    print(f'===== {name} ({p.stat().st_size} bytes) =====')
    r = subprocess.run(['protoc', '--decode_raw'], input=p.read_bytes(), capture_output=True)
    print(r.stdout.decode('utf-8', 'replace')[:30000])
    if r.stderr:
        print('ERR', r.stderr.decode('utf-8','replace'))

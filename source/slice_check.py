"""Local Bambu Studio slice check; never connects to a printer."""
from pathlib import Path
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
STUDIO = Path(os.environ.get('BAMBU_STUDIO') or shutil.which('bambu-studio')
              or shutil.which('bambu-studio.exe')
              or r'C:\Program Files\Bambu Studio\bambu-studio.exe')
PROFILES = Path(os.environ.get('BAMBU_STUDIO_PROFILES')
                or STUDIO.parent / 'resources' / 'profiles' / 'BBL')
OUTPUT = ROOT / 'manufacturing' / 'current'
OUTPUT.mkdir(exist_ok=True)


def resolve(kind, name, stack=()):
    assert name not in stack, 'Profile inheritance cycle'
    source = json.loads((PROFILES / kind / (name + '.json')).read_text(encoding='utf-8'))
    parent = source.get('inherits')
    result = resolve(kind, parent, stack + (name,)) if parent else {}
    for include in source.get('include', []):
        result.update(resolve(kind, include, stack + (name,)))
    result.update(source)
    for key in ('inherits', 'include'):
        result.pop(key, None)
    return result


machine = resolve('machine', 'Bambu Lab A1 0.4 nozzle')
process = resolve('process', '0.20mm Standard @BBL A1')
filament = resolve('filament', 'Generic PETG @BBL A1')
machine['printer_settings_id'] = machine['name']
process.update(wall_loops='4', enable_support='0', print_settings_id=process['name'])
filament['filament_settings_id'] = [filament['name']]
assert machine['printable_height'] == '256' and machine['bed_exclude_area'] == []
for name, data in [('machine', machine), ('process', process), ('filament', filament)]:
    (OUTPUT / (name + '.json')).write_text(json.dumps(data, indent=2), encoding='utf-8')
command = [str(STUDIO), '--debug', '2',
           '--arrange', '1', '--curr-bed-type', 'Textured PEI Plate',
           '--load-settings', str(OUTPUT / 'machine.json') + ';' + str(OUTPUT / 'process.json'),
           '--load-filaments', str(OUTPUT / 'filament.json'), '--slice', '0',
           '--outputdir', str(OUTPUT), '--export-3mf', 'bedside_shelf_v3_A1_PETG.3mf',
           '--export-settings', str(OUTPUT / 'resolved_settings.json'),
           str(ROOT / 'exports' / 'current' / 'bedside_shelf_v3.stl')]
(OUTPUT / 'command.json').write_text(json.dumps(command, indent=2), encoding='utf-8')
result = subprocess.run(command, cwd=OUTPUT, capture_output=True, timeout=600)
(OUTPUT / 'console.log').write_bytes(result.stdout + result.stderr)
print('Bambu Studio exit:', result.returncode)
print((OUTPUT / 'result.json').read_text(encoding='utf-8'))
assert result.returncode == 0
assert (OUTPUT / 'bedside_shelf_v3_A1_PETG.3mf').is_file()

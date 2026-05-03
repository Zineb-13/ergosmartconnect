from pathlib import Path
from subprocess import run, PIPE

path = Path('Dashboard/templates/Dossiers.html')
text = path.read_text(encoding='utf-8')
start = 21298
end = 23076
block = '\n'.join(text.splitlines()[start:end])
Path('tmp_mcro_check.js').write_text(block, encoding='utf-8')
print('wrote', len(block), 'chars')

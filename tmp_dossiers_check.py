from pathlib import Path
import re
path = Path('Dashboard/templates/Dossiers.html')
text = path.read_text(encoding='utf-8')
starts = [m.start() for m in re.finditer(r'<script(?:\s[^>]*)?>', text, re.IGNORECASE)]
ends = [m.start() for m in re.finditer(r'</script>', text, re.IGNORECASE)]
print('script starts', len(starts), 'ends', len(ends))
if len(starts) != len(ends):
    print('MISMATCH script tags')
for idx, s in enumerate(starts, 1):
    e = next((x for x in ends if x > s), None)
    if e is None:
        print('NO END for script', idx, 'start', s)
        continue
    code = text[text.find('>', s) + 1:e]
    if '</script>' in code:
        print('nested </script> in script block', idx)
    b = code.count('`')
    if b % 2 != 0:
        print('odd backticks in block', idx, 'count', b)
    if len(code) > 100000:
        print('block', idx, 'len', len(code), 'backticks', b)

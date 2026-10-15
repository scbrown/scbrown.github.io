#!/bin/sh
set -eu
printf '%s\n' 'Retained source baseline 6387d7aa: personal site has README + index; 0 compatibility HTML pages.'
python3 -m unittest discover -s tests -v
python3 - <<'PYINNER'
from pathlib import Path
from html.parser import HTMLParser
class Target(HTMLParser):
 def handle_starttag(self, tag, values):
  values=dict(values)
  if tag=='link' and values.get('rel')=='canonical': print(values['href'])
paths=list(Path('caboodle').glob('*.html'))
print('Actual compatibility HTML pages:',len(paths))
for name in ['index.html','introduction.html','reference.html']:
 print('/caboodle/'+name+' -> ',end='');Target().feed((Path('caboodle')/name).read_text())
PYINNER

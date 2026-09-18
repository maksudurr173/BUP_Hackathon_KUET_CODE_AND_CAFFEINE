import re, pathlib, json
root = pathlib.Path(__file__).parent
css = (root/'assets/css/styles.css').read_text()
def strip(p):
    s = (root/p).read_text()
    s = re.sub(r'^import .*?;\s*$', '', s, flags=re.M)
    s = re.sub(r'^export \{[^}]*\};\s*$', '', s, flags=re.M)
    s = re.sub(r'^export ', '', s, flags=re.M)
    return s
js = "\n".join(strip(p) for p in
    ['assets/js/samples.js','assets/js/charts.js','assets/js/engine.js','assets/js/app.js'])
html = (root/'index.html').read_text()
html = html.replace('<link rel="stylesheet" href="assets/css/styles.css">', '<style>\n'+css+'\n</style>')
html = html.replace('<script type="module" src="assets/js/app.js"></script>', '<script type="module">\n'+js+'\n</script>')
out = root/'gridwise-standalone.html'
out.write_text(html)
print('built', out, round(len(html)/1024), 'KB')

# чистка страниц от комментариев: html-комменты, /* */ в css, строчные // в js
# полные строки // удаляем только вне template-литералов, чтобы не задеть urls
import re, sys

files = sys.argv[1:] or [
    'front/assets/static/dash.html',
    'front/assets/static/course.html',
    'front/assets/static/index.html',
    'front/assets/static/profile.html',
    'front/assets/static/adminsecret.html',
    'front/assets/static/edit_course.html',
    'front/assets/static/tglogin.html',
]


def strip_block_comments(src):
    # /* ... */ — только если не внутри бэктиков: идем посимвольно
    out = []
    i, n = 0, len(src)
    in_tick = False
    while i < n:
        ch = src[i]
        if ch == '\\' and in_tick and i + 1 < n:
            out.append(src[i:i + 2]); i += 2; continue
        if ch == '`':
            in_tick = not in_tick; out.append(ch); i += 1; continue
        if not in_tick and ch == '/' and i + 1 < n and src[i + 1] == '*':
            end = src.find('*/', i + 2)
            if end == -1:
                break
            i = end + 2
            continue
        out.append(ch); i += 1
    return ''.join(out)


def strip_line_comments(js):
    # полные строки // вне template-литералов
    lines = js.splitlines()
    out = []
    in_tick = False
    for ln in lines:
        t = ln.lstrip()
        if not in_tick and t.startswith('//'):
            continue
        # считаем бэктики с учетом экранирования
        j, n = 0, len(ln)
        while j < n:
            ch = ln[j]
            if ch == '\\' and in_tick:
                j += 2; continue
            if ch == '`':
                in_tick = not in_tick
            j += 1
        out.append(ln)
    return '\n'.join(out)


def clean(src):
    # html-комменты (условных в проекте нет)
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    # стиль: блочные комменты
    def style_repl(m):
        return '<style>' + strip_block_comments(m.group(1)) + '</style>'
    src = re.sub(r'<style>(.*?)</style>', style_repl, src, flags=re.S)
    # скрипты: блочные + полные строчные
    def script_repl(m):
        js = strip_block_comments(m.group(1))
        js = strip_line_comments(js)
        return '<script>' + js + '</script>'
    src = re.sub(r'<script>(.*?)</script>', script_repl, src, flags=re.S)
    # схлопываем пустые строки
    src = re.sub(r'\n{3,}', '\n\n', src)
    return src


for f in files:
    before = open(f, encoding='utf-8').read()
    after = clean(before)
    if before != after:
        open(f, 'w', encoding='utf-8', newline='\n').write(after)
        print(f'{f}: {len(before)} -> {len(after)} bytes')
    else:
        print(f'{f}: clean')

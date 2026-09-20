# проверка js-скриптов страниц: парс + задвоенные const/let/function в одном скоупе
# esprima не знает ES2020 (`?.`), вычищаем перед парсом
import re
import esprima

files = [
    'front/assets/static/dash.html',
    'front/assets/static/course.html',
    'front/assets/static/index.html',
    'front/assets/static/profile.html',
    'front/assets/static/adminsecret.html',
    'front/assets/static/edit_course.html',
    'front/assets/static/tglogin.html',
]

# узлы, создающие новый скоуп (для let/const — блочная видимость)
SCOPE_NODES = ('Program', 'FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression',
               'BlockStatement', 'ForStatement', 'ForInStatement', 'ForOfStatement', 'SwitchCase',
               'CatchClause', 'TryStatement')


def walk(node, scope, errs, path, kind='var'):
    if not isinstance(node, dict) and not hasattr(node, '__dict__'):
        return
    if hasattr(node, 'type'):
        t = node.type
        if t in SCOPE_NODES:
            scope = {}
        # объявления в текущем скоупе
        name = None
        if t == 'VariableDeclarator' and getattr(node, 'id', None) is not None:
            if getattr(node.id, 'type', '') == 'Identifier' and kind in ('const', 'let'):
                name = node.id.name
        elif t == 'FunctionDeclaration' and getattr(node, 'id', None):
            name = node.id.name
        elif t == 'ClassDeclaration' and getattr(node, 'id', None):
            name = node.id.name
        if name:
            if name in scope:
                errs.append(f'дубликат объявления "{name}"')
            else:
                scope[name] = True
    # обходим детей
    if isinstance(node, dict):
        items = node.items()
    else:
        items = vars(node).items()
    for k, v in items:
        if k.startswith('_') or k == 'type':
            continue
        child_kind = getattr(v, 'kind', None) if k == 'declarations' and hasattr(v, 'kind') else kind
        if k == 'declarations' and hasattr(node, 'kind'):
            child_kind = node.kind
        if isinstance(v, (list, tuple)):
            for x in v:
                walk(x, scope, errs, path, child_kind or kind)
        elif hasattr(v, 'type') or isinstance(v, dict):
            walk(v, scope, errs, path, child_kind or kind)


bad = False
for f in files:
    src = open(f, encoding='utf-8').read()
    for i, m in enumerate(re.finditer(r'<script>(.*?)</script>', src, re.S)):
        body = m.group(1)
        if not body.strip():
            continue
        # optional chaining/nullish/catch-binding esprima не умеет — для проверки парса заменяем
        parseable = body.replace('?.', '.').replace('??', '||')
        parseable = re.sub(r'catch\s*\{', 'catch(e){', parseable)
        try:
            ast = esprima.parseScript(parseable)
        except Exception as e:
            bad = True
            print(f'SYNTAX_ERR {f} script#{i}: {str(e)[:140]}')
            continue
        errs = []
        walk(ast, {}, errs, f)
        if errs:
            bad = True
            for e in errs:
                print(f'DUP {f} script#{i}: {e}')
if not bad:
    print('ALL_OK')



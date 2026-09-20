# проверка разбора embed-кода (те же регекспы, что в редакторе)
import re

samples = [
    '<iframe width="560" height="315" src="https://www.youtube.com/embed/dQw4w9WgXcQ" title="YouTube" frameborder="0" allow="accelerometer; autoplay" allowfullscreen></iframe>',
    "<iframe src='https://rutube.ru/play/embed/abc123/'></iframe>",
    '<iframe src="https://vk.com/video_ext.php?oid=-123&id=456&hd=2" width="853" height="480" allowfullscreen></iframe>',
    '<script type="text/javascript" src="//vk.com/js/api/openapi.js?169"></script>',
    'https://youtu.be/dQw4w9WgXcQ',
]

for s in samples:
    ifm = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', s, re.I)
    scr = re.search(r'<script[^>]+src=["\']([^"\']+)["\']', s, re.I)
    if ifm:
        print('IFRAME ->', ifm.group(1))
    elif scr:
        print('SCRIPT ->', scr.group(1))
    else:
        print('URL    ->', s)

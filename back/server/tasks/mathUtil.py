# ! back/server/tasks/mathUtil.py
# мини-инструмент по математике: сложение / вычитание / умножение / деление
# структура ответа совместима с biologyUtil, чтобы проверка/подсказки работали одинаково
import random

MODE_ADDITION = 1
MODE_SUBTRACTION = 2
MODE_MULTIPLICATION = 3
MODE_DIVISION = 4

MATH_MODES = {
    MODE_ADDITION: 'сложение',
    MODE_SUBTRACTION: 'вычитание',
    MODE_MULTIPLICATION: 'умножение',
    MODE_DIVISION: 'деление',
}

# границы чисел по сложности: (меньше, больше) — больший диапазон = сложнее
DIFFICULTY_RANGE = {
    'easy': (1, 20),
    'hard': (10, 200),
}


def _range(difficulty: str | None) -> tuple[int, int]:
    return DIFFICULTY_RANGE.get((difficulty or 'easy').lower(), DIFFICULTY_RANGE['easy'])


def _rand(lo: int, hi: int) -> int:
    return random.randint(max(1, lo), max(lo, hi))


def _plus(a: int, b: int) -> str:
    return f'{a} + {b}'


def _minus(a: int, b: int) -> str:
    return f'{a} − {b}'


def _times(a: int, b: int) -> str:
    return f'{a} × {b}'


def _divide(a: int, b: int) -> str:
    return f'{a} ÷ {b}'


def _normalize_answer(value) -> float | None:
    """Ответ приходит строкой: «19», «19,5», «-4», «1 234». Возвращаем число или None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace('\u2212', '-').replace('\u2013', '-')
    text = text.replace(' ', '').replace('\u00a0', '').replace(',', '.')
    if not text:
        return None
    # иногда пишут «= 19» или «ответ: 19» — оставляем последний числовой кусок
    allowed = '0123456789.-'
    cleaned = ''.join(ch for ch in text if ch in allowed)
    if cleaned in ('', '-', '.', '-.'):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


async def generate_task(mode: int, difficulty: str = 'easy', settings: dict | None = None):
    """Собирает задание с тем же контрактом, что и biologyUtil.generate_task:
    mode / task_id / condition / internal_solution / tryings
    """
    try:
        mode = int(mode)
    except (TypeError, ValueError):
        mode = MODE_ADDITION
    if mode not in MATH_MODES:
        mode = MODE_ADDITION

    settings = settings or {}
    lo, hi = _range(settings.get('difficulty') or difficulty)
    # settings может сузить/расширить диапазон (maxValue из редактора задач)
    max_value = settings.get('maxValue')
    if isinstance(max_value, (int, float)) and max_value > 1:
        hi = int(max_value)
        lo = min(lo, max(1, hi // 4))

    if mode == MODE_ADDITION:
        a, b = _rand(lo, hi), _rand(lo, hi)
        expression, answer = _plus(a, b), a + b
        instruction = 'Сложение: найди значение выражения'
    elif mode == MODE_SUBTRACTION:
        a, b = _rand(lo, hi), _rand(lo, hi)
        if b > a:  # без отрицательных результатов на лёгком уровне
            a, b = b, a
        expression, answer = _minus(a, b), a - b
        instruction = 'Вычитание: найди значение выражения'
    elif mode == MODE_MULTIPLICATION:
        # таблицу умножения берём шире, но множители держим небольшими
        top = 10 if (settings.get('difficulty') or difficulty) != 'hard' else 25
        a, b = random.randint(2, max(2, min(hi, top))), random.randint(2, 12)
        expression, answer = _times(a, b), a * b
        instruction = 'Умножение: найди значение выражения'
    else:  # MODE_DIVISION — делится всегда нацело, чтобы ответ был целым
        divisor = random.randint(2, 12 if (settings.get('difficulty') or difficulty) != 'hard' else 25)
        quotient = random.randint(2, max(2, min(hi, 25)))
        dividend = divisor * quotient
        expression, answer = _divide(dividend, divisor), quotient
        instruction = 'Деление: найди значение выражения (делится нацело)'

    task = {
        'mode': mode,
        'task_id': random.randint(10_000_000, 999_999_999),
        'condition': {
            'kind': 'math',
            'mode': mode,
            'mode_name': MATH_MODES[mode],
            'expression': expression,
            'instruction': instruction,
        },
        'internal_solution': {
            'kind': 'math',
            'type': 'number',
            'answer': answer,
            'canonical': str(answer),
            'canonical_5_3': str(answer),  # для совместимости с подсказками
        },
        'tryings': 0,
    }
    return task


async def validate_submission(user_input: str, solution: dict):
    """Проверка ответа. Контракт как у biologyUtil.validate_submission."""
    expected = solution.get('answer')
    if expected is None:
        expected = _normalize_answer(solution.get('canonical'))
    if expected is None:
        return {
            'is_correct': False,
            'score': 0,
            'errors': [{'type': 'TASK', 'msg': 'условие задания повреждено'}],
        }

    got = _normalize_answer(user_input)
    if got is None:
        return {
            'is_correct': False,
            'score': 0,
            'errors': [{'type': 'FORMAT', 'msg': 'введите число, например 42'}],
        }

    expected_f = float(expected)
    # числа целые: сравниваем с допуском на случай «19,0»
    if abs(got - expected_f) < 1e-9:
        return {'is_correct': True, 'score': 100, 'errors': []}

    return {
        'is_correct': False,
        'score': 0,
        'errors': [{
            'type': 'VALUE',
            'msg': 'ответ не совпадает с верным',
        }],
    }

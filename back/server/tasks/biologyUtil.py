import random
import asyncio
from typing import Dict, Any, List, Tuple, Optional

# ==========================================
# 1. КОНФИГУРАЦИЯ И БИОЛОГИЧЕСКИЕ КОНСТАНТЫ
# ==========================================

DNA_NUCS = ['А', 'Т', 'Г', 'Ц']
# Словари комплементарности
DNA_COMP = {'А': 'Т', 'Т': 'А', 'Г': 'Ц', 'Ц': 'Г'}
DNA_TO_RNA = {'А': 'У', 'Т': 'А', 'Г': 'Ц', 'Ц': 'Г'}

# ==========================================
# 2. ЯДРО (ГЕНЕРАЦИЯ И ТРАНСФОРМАЦИЯ)
# ==========================================

async def generate_sequence(length: int) -> str:
    return "".join(random.choice(DNA_NUCS) for _ in range(length))

async def get_complement(seq: str, mapping: dict) -> str:
    """Возвращает комплементарную последовательность (без переворота)."""
    return "".join(mapping[n] for n in seq)

async def get_reverse(seq: str) -> str:
    return seq[::-1]

# ==========================================
# 3. ЛОГИКА ЗАДАЧ (REPOSITORIES/SERVICE)
# ==========================================

async def generate_task(mode: int, length: int = 18) -> Dict[str, Any]:
    """
    Генерирует задачу в зависимости от режима.
    Возвращает условие (condition) и эталонный ответ (canonical_answer) в формате 5'->3'.
    """
    # Генерируем верхнюю цепь ДНК (всегда 5'->3' по умолчанию для генератора)
    top_dna = await generate_sequence(length)
    
    # Генерируем нижнюю цепь (3'<-5', комплементарна верхней)
    # В визуализации она будет записана как 3'-...-5'
    bottom_dna_raw = await get_complement(top_dna, DNA_COMP) # Это 3'->5'
    
    response = {
        "mode": mode,
        "task_id": random.randint(10000000, 999999999),
        "condition": {},
        "internal_solution": {} # Скрыто от фронтенда
    }

    if mode == 1:
        # Режим 1: Транскрибируемая - НИЖНЯЯ.
        # Значит, РНК строится по нижней. РНК будет похожа на ВЕРХНЮЮ (Т->У).
        # Эталон (5'->3'):
        mrna_5_3 = await get_complement(bottom_dna_raw, DNA_TO_RNA) 
        
        response["condition"] = {
            "top": f"5'-{top_dna}-3'",
            "bottom": f"3'-{bottom_dna_raw}-5'",
            "instruction": "Нижняя цепь транскрибируемая. Введите мРНК:"
        }
        response["internal_solution"] = {
            "type": "RNA",
            "canonical_5_3": mrna_5_3
        }

    elif mode == 2:
        # Режим 2: Транскрибируемая - ВЕРХНЯЯ.
        # РНК строится по верхней. РНК комплементарна верхней.
        # Эталон (5'->3'): Поскольку верхняя читается 3'<-5', РНК синтезируется 5'->3'.
        # Нам нужно взять комплементарность к верхней и развернуть её, чтобы получить 5'->3' вид.
        comp = await get_complement(top_dna, DNA_TO_RNA) # Это направление 3'->5' (антипараллельно верхней)
        mrna_5_3 = await get_reverse(comp) # Переворачиваем в стандарт 5'->3'
        
        response["condition"] = {
            "top": f"5'-{top_dna}-3'",
            "bottom": f"3'-{bottom_dna_raw}-5'",
            "instruction": "Верхняя цепь транскрибируемая. Введите мРНК:"
        }
        response["internal_solution"] = {
            "type": "RNA",
            "canonical_5_3": mrna_5_3
        }

    elif mode == 3:
        # Режим 3: Создание транскрибируемой ДНК.
        # Дана только одна цепь (пусть будет 5'->3'). Нужно построить вторую ДНК.
        # Эталон (5'->3' вид для второй цепи): это перевернутая комплементарная цепь (нижняя).
        # Но пользователь скорее всего захочет ввести её как 3'-...-5'.
        
        # Каноническая форма второй цепи (если читать её от 5' к 3'):
        second_strand_5_3 = await get_reverse(bottom_dna_raw)
        
        response["condition"] = {
            "single_chain": f"5'-{top_dna}-3'",
            "instruction": "Постройте транскрибируемую цепь ДНК (комплементарную):"
        }
        response["internal_solution"] = {
            "type": "DNA",
            "canonical_5_3": second_strand_5_3
        }
    response['tryings'] = 0
    return response

# ==========================================
# 4. ВАЛИДАТОР (ПРОВЕРКА ОТВЕТА)
# ==========================================

async def validate_submission(user_input: str, solution_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Проверяет ввод пользователя. Учитывает направление 5'-3' или 3'-5'.
    """
    # 1. Парсинг ввода
    # Ожидаем формат: "5'-АААГГЦ-3'" или "3'-ЦГГААА-5'"
    # Удаляем пробелы
    clean_input = user_input.replace(" ", "").upper()
    
    # Определяем концы
    start_label = clean_input[:2]  # "5'" или "3'"
    end_label = clean_input[-2:]   # "3'" или "5'"
    
    sequence_part = clean_input[3:-3] # Вырезаем саму последовательность (между тире)
    # Если пользователь не поставил тире (например 5'АГЦ3'), пробуем адаптивный срез:
    if '-' not in clean_input:
        start_label = clean_input[:2]
        end_label = clean_input[-2:]
        sequence_part = clean_input[2:-2]

    canonical_seq = solution_data["canonical_5_3"]
    
    errors = []
    parsed_direction = "unknown"

    # 2. Нормализация последовательности пользователя к стандарту 5'->3'
    user_seq_normalized = ""
    
    if start_label == "5'" and end_label == "3'":
        # Пользователь ввел в прямом направлении (стандарт)
        parsed_direction = "forward"
        user_seq_normalized = sequence_part
        
    elif start_label == "3'" and end_label == "5'":
        # Пользователь ввел в обратном направлении.
        # Чтобы сравнить с каноническим (который 5'->3'), нам нужно перевернуть ввод пользователя.
        parsed_direction = "reverse"
        user_seq_normalized = await get_reverse(sequence_part)
        
    else:
        # Ошибка в концах цепи
        if start_label not in ["5'", "3'"]:
            errors.append({"type": "WRONG_START", "msg": f"Неверный 5'-конец (обнаружено {start_label})"})
        if end_label not in ["5'", "3'"]:
            errors.append({"type": "WRONG_END", "msg": f"Неверный 3'-конец (обнаружено {end_label})"})
        if start_label == end_label:
            errors.append({"type": "IMPOSSIBLE_DIRECTION", "msg": "Концы цепи не могут быть одинаковыми"})
            
        return {"is_correct": False, "errors": errors, "score": 0}

    # 3. Посимвольная проверка
    # Сравниваем нормализованный ввод с каноническим эталоном
    
    # Проверка длины
    if len(user_seq_normalized) != len(canonical_seq):
        return {
            "is_correct": False, 
            "errors": [{"type": "LENGTH", "msg": "Длина цепи не совпадает"}],
            "score": 0
        }

    mismatches = []
    for i in range(len(canonical_seq)):
        if user_seq_normalized[i] != canonical_seq[i]:
            # Важно: индекс ошибки возвращаем для ОТОБРАЖЕНИЯ. 
            # Если пользователь писал 3'->5', то визуально индекс i (в нормализованной строке)
            # соответствует индексу (len - 1 - i) в его строке ввода.
            
            visual_index = i if parsed_direction == "forward" else (len(canonical_seq) - 1 - i)
            
            mismatches.append({
                "index": visual_index, 
                "expected": canonical_seq[i] if parsed_direction == "forward" else canonical_seq[len(canonical_seq)-1-i],
                "got": user_seq_normalized[i]
            })

    if not mismatches:
        return {"is_correct": True, "score": 100, "errors": []}
    else:
        return {
            "is_correct": False, 
            "score": max(0, 100 - len(mismatches)*10),
            "errors": mismatches,
            "direction_used": parsed_direction
        }
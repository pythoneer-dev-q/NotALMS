import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from back.server.database.coursesDB import total_points_for_row
from back.server.database import utils
from back.server.handlers.front_apiHandler import (
    _generate_variant,
    _max_wrong_attempts,
    _one_variant_per_student,
    _validate_submission,
)
from back.server.handlers.fronthandler_conf.models import RegVisibleCourse
from back.server.handlers.teacher_handler import _owned_roles
from back.server.runtime import _expected_disconnect
from back.server.tasks import biologyUtil


class RuntimeTests(unittest.TestCase):
    def test_expected_network_disconnects_are_recognized(self):
        self.assertTrue(_expected_disconnect({'exception': ConnectionResetError('reset')}))
        self.assertTrue(_expected_disconnect({
            'message': 'Exception in callback _SelectorSocketTransport._call_connection_lost',
            'exception': AttributeError('transport is already cleared'),
        }))
        self.assertFalse(_expected_disconnect({'exception': ValueError('application bug')}))

    def test_legacy_progress_total_is_reconstructed(self):
        self.assertEqual(
            total_points_for_row({'solve_count': 4, 'base_points': 100, 'points': 800}),
            1500,
        )
        self.assertEqual(total_points_for_row({'total_points': 1700}), 1700)


class QuizTests(unittest.IsolatedAsyncioTestCase):
    async def test_jwt_rejects_unknown_or_missing_claims(self):
        valid = await utils.create_access_token({'role': 'user', 'user_uid': 'user-1'})
        self.assertEqual((await utils.decode_token(valid))['user_uid'], 'user-1')

        extra = await utils.create_access_token({
            'role': 'user', 'user_uid': 'user-1', 'legacy_field': 'remove me',
        })
        self.assertIsNone(await utils.decode_token(extra))

        missing_uid = await utils.create_access_token({'role': 'user'})
        self.assertIsNone(await utils.decode_token(missing_uid))

        blocked = await utils.create_access_token(
            {'role': 'user', 'user_uid': 'user-1', 'blocked': True}, expires=False,
        )
        self.assertTrue((await utils.decode_token(blocked))['blocked'])
        malformed_blocked = await utils.create_access_token(
            {'role': 'user', 'user_uid': 'user-1', 'blocked': True},
        )
        self.assertIsNone(await utils.decode_token(malformed_blocked))

    async def test_quiz_keeps_correct_answers_server_side(self):
        definition = {
            'type': 'quiz',
            'mode': 'quiz',
            'settings': {'variants': [{
                'question': '2 + 2',
                'answers': [
                    {'id': 'a', 'text': '3', 'correct': False},
                    {'id': 'b', 'text': '4', 'correct': True},
                ],
            }]},
        }
        variant = await _generate_variant(definition)
        self.assertNotIn('correct', repr(variant['condition']))
        self.assertTrue((await _validate_submission(
            'quiz', ['b'], variant['internal_solution'],
        ))['is_correct'])
        self.assertFalse((await _validate_submission(
            'quiz', ['a'], variant['internal_solution'],
        ))['is_correct'])

    async def test_matching_task_generation_and_validation(self):
        definition = {
            'type': 'quiz',
            'mode': 'quiz',
            'settings': {'variants': [{
                'kind': 'matching',
                'question': 'Установите соответствие',
                'pairs': [
                    {'left': 'Митохондрия', 'right': 'Синтез АТФ'},
                    {'left': 'Рибосома', 'right': 'Синтез белка'},
                ],
            }]},
        }
        variant = await _generate_variant(definition)
        cond = variant['condition']
        self.assertEqual(cond['kind'], 'matching')
        self.assertEqual(len(cond['left_items']), 2)
        self.assertEqual(len(cond['right_items']), 2)

        sol = variant['internal_solution']
        correct_input = sol['pairs']  # e.g. {'L0': 'R0', 'L1': 'R1'}
        self.assertTrue((await _validate_submission('quiz', correct_input, sol))['is_correct'])

        # Valid as list of pairs
        pair_list = list(correct_input.items())
        self.assertTrue((await _validate_submission('quiz', pair_list, sol))['is_correct'])

        # Wrong pair
        wrong_input = {'L0': 'R1', 'L1': 'R0'}
        self.assertFalse((await _validate_submission('quiz', wrong_input, sol))['is_correct'])

    async def test_matching_task_type_and_validation(self):
        definition = {
            'type': 'matching',
            'mode': 'quiz',
            'settings': {'variants': [{
                'kind': 'matching',
                'question': 'Соедините органоиды и их функции',
                'pairs': [
                    {'left': 'Хлоропласт', 'right': 'Фотосинтез'},
                    {'left': 'Митохондрия', 'right': 'Синтез АТФ'},
                ],
            }]},
        }
        variant = await _generate_variant(definition)
        cond = variant['condition']
        self.assertEqual(cond['kind'], 'matching')
        sol = variant['internal_solution']
        self.assertEqual(sol['kind'], 'matching')

        # Test validation with 'matching' task type
        self.assertTrue((await _validate_submission('matching', sol['pairs'], sol))['is_correct'])
        self.assertFalse((await _validate_submission('matching', {'L0': 'R99'}, sol))['is_correct'])

    async def test_quiz_supports_multiple_correct_answers(self):
        definition = {
            'type': 'quiz',
            'mode': 'quiz',
            'settings': {'variants': [{
                'question': 'Выберите чётные числа',
                'answers': [
                    {'id': 'one', 'text': '1', 'correct': False},
                    {'id': 'two', 'text': '2', 'correct': True},
                    {'id': 'four', 'text': '4', 'correct': True},
                ],
            }]},
        }

        variant = await _generate_variant(definition)

        self.assertTrue(variant['condition']['multiple'])
        self.assertTrue((await _validate_submission(
            'quiz', ['four', 'two'], variant['internal_solution'],
        ))['is_correct'])
        self.assertFalse((await _validate_submission(
            'quiz', ['two'], variant['internal_solution'],
        ))['is_correct'])

    async def test_quiz_variant_is_stable_for_student(self):
        definition = {
            'type': 'quiz',
            'settings': {
                'one_variant_per_student': True,
                'variants': [
                    {'question': f'Вариант {index}', 'answers': [
                        {'id': 'yes', 'text': 'Да', 'correct': True},
                        {'id': 'no', 'text': 'Нет', 'correct': False},
                    ]}
                    for index in range(8)
                ],
            },
        }

        first = await _generate_variant(definition, variant_key='student-1:task-1')
        second = await _generate_variant(definition, variant_key='student-1:task-1')

        self.assertEqual(first['condition']['question'], second['condition']['question'])
        self.assertTrue(_one_variant_per_student(definition))

    async def test_quiz_supports_image(self):
        definition = {
            'type': 'quiz',
            'mode': 'quiz',
            'settings': {'variants': [{
                'question': 'Назовите структуру на рисунке',
                'image': 'https://example.com/cell.png',
                'answers': [
                    {'id': 'a', 'text': 'Митохондрия', 'correct': True},
                    {'id': 'b', 'text': 'Рибосома', 'correct': False},
                ],
            }]},
        }
        variant = await _generate_variant(definition)
        self.assertEqual(variant['condition'].get('image'), 'https://example.com/cell.png')
        self.assertTrue((await _validate_submission(
            'quiz', ['a'], variant['internal_solution'],
        ))['is_correct'])

    def test_wrong_attempt_limit_is_normalized(self):
        self.assertEqual(_max_wrong_attempts({'settings': {'max_wrong_attempts': 5}}), 5)
        self.assertEqual(_max_wrong_attempts({'settings': {'max_wrong_attempts': -2}}), 0)
        self.assertEqual(_max_wrong_attempts({'settings': {'max_wrong_attempts': 999}}), 100)
        self.assertEqual(_max_wrong_attempts({'settings': {}}), 0)


class TeacherRoleAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_roles_accepts_and_deduplicates_teacher_groups(self):
        owned_role = AsyncMock(side_effect=[{'role_id': 'group-1'}, {'role_id': 'group-2'}])
        with patch('back.server.handlers.teacher_handler.accessDB.owned_role', owned_role):
            result = await _owned_roles('teacher-1', ['group-1', 'group-2', 'group-1'])

        self.assertEqual(result, ['group-1', 'group-2'])
        self.assertEqual(owned_role.await_count, 2)

    async def test_owned_roles_rejects_foreign_group(self):
        owned_role = AsyncMock(side_effect=[{'role_id': 'group-1'}, None])
        with patch('back.server.handlers.teacher_handler.accessDB.owned_role', owned_role):
            with self.assertRaises(HTTPException) as error:
                await _owned_roles('teacher-1', ['group-1', 'group-2'])

        self.assertEqual(error.exception.status_code, 403)


class CourseValidationTests(unittest.TestCase):
    def test_course_description_is_limited(self):
        payload = {
            'id': 'course-1', 'title': 'Курс', 'description': 'x' * 501,
            'cover': '', 'difficulty': 'easy', 'tags': [], 'lessons': [],
            'granted_to': [],
        }
        with self.assertRaises(ValidationError):
            RegVisibleCourse(**payload)


class BiologyInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_direction_accepts_common_quote_styles(self):
        solution = {'canonical_5_3': 'АТГЦ'}
        answers = [
            "5'-АТГЦ-3'",
            '5’-АТГЦ-3’',
            '5"-АТГЦ-3"',
            '5«-АТГЦ-3»',
            '5′-АТГЦ-3′',
            '5`-АТГЦ-3`',
        ]

        for answer in answers:
            with self.subTest(answer=answer):
                result = await biologyUtil.validate_submission(answer, solution)
                self.assertTrue(result['is_correct'])

    async def test_protein_biosynthesis_generation_and_validation(self):
        task = await biologyUtil.generate_task(mode=4, length=12)
        self.assertEqual(task['mode'], 4)
        self.assertIn('mrna', task['condition'])
        self.assertTrue(task['condition'].get('table_hint'))
        canonical = task['internal_solution']['canonical']
        self.assertTrue(len(canonical) > 0)
        # Test exact match
        res = await biologyUtil.validate_submission(canonical, task['internal_solution'])
        self.assertTrue(res['is_correct'])
        # Test lowercase with spaces
        res_spaced = await biologyUtil.validate_submission(canonical.lower().replace('-', ' '), task['internal_solution'])
        self.assertTrue(res_spaced['is_correct'])
        # Test incorrect answer
        res_wrong = await biologyUtil.validate_submission('НЕВЕРНЫЙ-ОТВЕТ', task['internal_solution'])
        self.assertFalse(res_wrong['is_correct'])

    async def test_anticodons_generation_and_validation(self):
        task = await biologyUtil.generate_task(mode=5, length=9)
        self.assertEqual(task['mode'], 5)
        self.assertIn('codons', task['condition'])
        canonical = task['internal_solution']['canonical']
        res = await biologyUtil.validate_submission(canonical, task['internal_solution'])
        self.assertTrue(res['is_correct'])

    async def test_interactive_nucleotide_generation_and_validation(self):
        task = await biologyUtil.generate_task(mode=6)
        self.assertEqual(task['mode'], 6)
        sol = task['internal_solution']
        correct_sub = {
            'sugar': sol['sugar'],
            'base': sol['base'],
            'has_phosphate': sol['has_phosphate']
        }
        res = await biologyUtil.validate_submission(correct_sub, sol)
        self.assertTrue(res['is_correct'])
        # Wrong base
        wrong_sub = {
            'sugar': sol['sugar'],
            'base': 'НЕ_ТА_БАЗА',
            'has_phosphate': sol['has_phosphate']
        }
        res_wrong = await biologyUtil.validate_submission(wrong_sub, sol)
        self.assertFalse(res_wrong['is_correct'])

    async def test_interactive_chain_generation_and_validation(self):
        task = await biologyUtil.generate_task(mode=7, length=4)
        self.assertEqual(task['mode'], 7)
        sol = task['internal_solution']
        seq = sol['sequence']
        # Valid string
        res = await biologyUtil.validate_submission(seq, sol)
        self.assertTrue(res['is_correct'])
        # Valid list of chars
        res_list = await biologyUtil.validate_submission(list(seq), sol)
        self.assertTrue(res_list['is_correct'])
        # Wrong seq
        res_wrong = await biologyUtil.validate_submission('ЦЦЦЦ', sol)
        if seq != 'ЦЦЦЦ':
            self.assertFalse(res_wrong['is_correct'])

    async def test_interactive_cloverleaf_generation_and_validation(self):
        task = await biologyUtil.generate_task(mode=8)
        self.assertEqual(task['mode'], 8)
        sol = task['internal_solution']
        correct_sub = {
            'anticodon': sol['anticodon'],
            'paired': True
        }
        res = await biologyUtil.validate_submission(correct_sub, sol)
        self.assertTrue(res['is_correct'])
        wrong_sub = {
            'anticodon': 'ZZZ',
            'paired': True
        }
        res_wrong = await biologyUtil.validate_submission(wrong_sub, sol)
        self.assertFalse(res_wrong['is_correct'])


if __name__ == '__main__':
    unittest.main()

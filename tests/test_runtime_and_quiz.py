import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from back.server.database.coursesDB import total_points_for_row
from back.server.database import utils
from back.server.handlers.front_apiHandler import _generate_variant, _validate_submission
from back.server.handlers.teacher_handler import _owned_roles
from back.server.runtime import _expected_disconnect


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


if __name__ == '__main__':
    unittest.main()

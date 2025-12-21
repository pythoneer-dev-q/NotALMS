import requests
"""_id=data.id, 
        lesson_id=data.lesson_id,
        mode=data.mode,
        settings=data.settings,
        task_type=data.type_task,
        difficulty=data.difficulty
    """
response = requests.post(
    'http://localhost:8004/v1/createTask',
    json={
    "id": "testCourseLesson12",
    "lesson_id": "testCourseLesson1",
    "mode": 'createRNK',
    'settings': {
        'taskLen': 10
    },
    'type_task': 'test',
    'difficulty': 'hard'
}
)
print(response.text)


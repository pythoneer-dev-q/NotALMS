import requests

response = requests.post(
    'http://localhost:8004/v1/createLesson',
    json={
    "id": "testCourseLesson2",
    "course_id": "testCourse",
    "title": "Строение рНК",
    "type": "theory",
    "order": 2,
    "content": [
        {
            "type": "text",
            "value": "РРРРРнкккк"
        },
        {
            "type": "image",
            "src": "/static/img/dna.png",
            "alt": "Структура ароырваоыНК"
        },
        {
            "type": "list",
            "items": [
                "test1",
                "Test1",
                "TesT1",
                "Цитози2н"
            ]
        },
    ]
}
)
print(response.text)


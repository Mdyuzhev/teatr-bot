"""
Общие фикстуры для тестов театрального бота.
"""
import pytest


@pytest.fixture
def kudago_event_fixture() -> dict:
    """Пример ответа KudaGo API для одного события — используется во всех unit-тестах."""
    return {
        "id": 123456,
        "title": "Вишнёвый сад",
        "slug": "vishnyovyi-sad-mkhat",
        "body_text": "Классический спектакль МХТ по Чехову.",
        "tags": [{"slug": "spektakl"}, {"slug": "drama"}],
        "age_restriction": 12,
        "price": "1000-5000 руб",
        "place": {
            "id": 789,
            "title": "МХТ им. Чехова",
            "slug": "mkhat-chekhova",
            "address": "Камергерский пер., 3",
            "subway": "Охотный Ряд",
            "site_url": "https://mxat.ru"
        },
        "dates": [
            {
                "start": 1742400000,
                "price": "1500-3000 руб"
            }
        ]
    }


@pytest.fixture
def kudago_premiere_fixture() -> dict:
    """Пример события с тегом 'премьера'."""
    return {
        "id": 999,
        "title": "Новый спектакль — Премьера",
        "slug": "novyi-spektakl-premiera",
        "body_text": "Долгожданная премьера сезона.",
        "tags": [{"slug": "premera"}, {"slug": "drama"}],
        "age_restriction": 16,
        "price": "от 2000 руб",
        "place": {
            "id": 100,
            "title": "Театр Вахтангова",
            "slug": "vakhtangov",
            "address": "Арбат, 26",
            "subway": "Арбатская",
            "site_url": "https://www.vakhtangov.ru"
        },
        "dates": [
            {
                "start": 1742486400,
                "price": "от 2000 руб"
            }
        ]
    }

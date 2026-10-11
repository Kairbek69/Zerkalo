"""
anticorruption_mastery.py
Модуль защиты от мошенничества.
Часть системы "Зеркало".
"""
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class ScamScheme:
    code: str
    title: str
    how_offered: str
    what_really: str
    law_article: str
    punishment: str


@dataclass
class UserWarning:
    level: str
    message: str
    action: str
    timestamp: str = ""


SCHEMES = {
    "SIM_FRAUD": ScamScheme(
        code="SIM_FRAUD",
        title="Оформление SIM-карты на себя",
        how_offered="«Оформи симку на своё имя и отдай нам. За это 10–20 тысяч тенге.»",
        what_really="С этой SIM звонят мошенники. Полиция идёт по номеру. Номер оформлен на тебя.",
        law_article="Ст. 190 УК РК (Мошенничество), соучастие",
        punishment="До 7 лет лишения свободы + возмещение ущерба",
    ),
    "CARD_RENTAL": ScamScheme(
        code="CARD_RENTAL",
        title="Аренда банковской карты (дроп)",
        how_offered="«Дай карту на пару дней. Придут деньги, 10% твои.»",
        what_really="На карту приходят деньги от преступлений. Ты их снимаешь и передаёшь.",
        law_article="Ст. 190 УК РК + Ст. 174 УК РК (Легализация)",
        punishment="До 7 лет + конфискация + долг потерпевшим",
    ),
    "P2P_CRYPTO": ScamScheme(
        code="P2P_CRYPTO",
        title="P2P / крипто-обмен",
        how_offered="«Тебе кинут деньги, ты переведёшь дальше. Это крипта, всё чисто.»",
        what_really="Ты переводишь чужие деньги — деньги жертв мошенников.",
        law_article="Ст. 174 УК РК + Ст. 190 УК РК",
        punishment="До 7 лет лишения свободы + конфискация",
    ),
    "MONEY_MULE": ScamScheme(
        code="MONEY_MULE",
        title="Переводы «для других»",
        how_offered="«Просто получи перевод и передай дальше. Тебе процент.»",
        what_really="Ты становишься звеном в цепочке отмывания денег.",
        law_article="Ст. 174 УК РК",
        punishment="До 6 лет + конфискация",
    ),
    "PHONE_SCAM": ScamScheme(
        code="PHONE_SCAM",
        title="Телефонный обман («родственник в беде»)",
        how_offered="«Ваш сын попал в беду. Срочно нужны деньги.»",
        what_really="Классическая схема. Играют на страхе и панике.",
        law_article="Ст. 190 УК РК",
        punishment="Для мошенника — до 7 лет",
    ),
    "INVEST_SCAM": ScamScheme(
        code="INVEST_SCAM",
        title="Инвестиции / пирамиды",
        how_offered="«Вложи 100 тысяч — получишь миллион за месяц.»",
        what_really="Финансовая пирамида. Первым платят из денег следующих.",
        law_article="Ст. 190 УК РК + Ст. 217 УК РК",
        punishment="Для организаторов — до 7 лет",
    ),
}


def check_offer(text: str) -> Optional[UserWarning]:
    """Проверяет текст на признаки мошенничества."""
    text_lower = text.lower()

    triggers = {
        "SIM_FRAUD": ["оформи сим", "сим-карт", "симка на себя", "sim на себя"],
        "CARD_RENTAL": ["дай карту", "аренда карты", "карта в аренду", "10 процентов"],
        "P2P_CRYPTO": ["p2p", "крипт", "обмен", "переведи дальше"],
        "MONEY_MULE": ["получи перевод", "передай дальше", "переводы для других"],
        "PHONE_SCAM": ["родственник в беде", "сын попал", "срочно деньги"],
        "INVEST_SCAM": ["инвестиц", "пирамид", "вложи получишь"],
    }

    for code, words in triggers.items():
        for word in words:
            if word in text_lower:
                scheme = SCHEMES[code]
                return UserWarning(
                    level="красный",
                    message=(
                        f"⚠️ ВНИМАНИЕ: похоже на схему «{scheme.title}».\n\n"
                        f"Как предлагают: {scheme.how_offered}\n\n"
                        f"Что на самом деле: {scheme.what_really}\n\n"
                        f"Статья: {scheme.law_article}\n"
                        f"Наказание: {scheme.punishment}"
                    ),
                    action=f"НЕ соглашайтесь. Схема: {code}",
                )
    return None


def list_schemes() -> List[str]:
    return [s.title for s in SCHEMES.values()]

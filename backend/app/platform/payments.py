"""Способы оплаты платформы.

Единый список для кабинета арендатора и панели платформы. Платёжные адаптеры
подключаются по мере готовности договоров с провайдерами; до этого доступны
банковский перевод и наличные с ручным подтверждением.
"""

from __future__ import annotations

from dataclasses import dataclass


STATUS_AVAILABLE = "available"
STATUS_SETUP = "setup"


@dataclass(frozen=True)
class PaymentMethod:
    code: str
    title: str
    description: str
    instructions: str
    status: str
    icon: str


PAYMENT_METHODS = (
    PaymentMethod(
        "bank_transfer",
        "Банковский перевод",
        "По счёту на расчётный счёт платформы",
        "Укажите номер счёта в назначении платежа. После поступления денег "
        "платформа подтвердит оплату, тариф включится автоматически.",
        STATUS_AVAILABLE,
        "wallet",
    ),
    PaymentMethod(
        "card",
        "Карта (bePaid)",
        "Visa, Mastercard, БЕЛКАРТ",
        "Оплата картой на защищённой странице провайдера. Способ подключается "
        "после заключения договора эквайринга.",
        STATUS_SETUP,
        "card",
    ),
    PaymentMethod(
        "erip",
        "ЕРИП",
        "Оплата в банках и инфокиосках",
        "Счёт с кодом платежа и номером. Способ подключается после регистрации "
        "в системе ЕРИП.",
        STATUS_SETUP,
        "receipt",
    ),
    PaymentMethod(
        "cash",
        "Наличными в офисе",
        "Оплата при подписании документов",
        "Оплатите в офисе платформы. Сотрудник подтвердит платёж в панели.",
        STATUS_AVAILABLE,
        "wallet",
    ),
    PaymentMethod(
        "terminal",
        "Терминал / эквайринг",
        "Оплата картой на месте",
        "Для офиса и выездного подключения. Требуется договор эквайринга.",
        STATUS_SETUP,
        "card",
    ),
)


def methods_payload() -> list[dict]:
    return [
        {
            "code": item.code,
            "title": item.title,
            "description": item.description,
            "instructions": item.instructions,
            "status": item.status,
            "icon": item.icon,
        }
        for item in PAYMENT_METHODS
    ]

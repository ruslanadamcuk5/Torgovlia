"""Демо-наборы услуг и специалистов для сервисных категорий.

Формат: категория → услуги. Длительность в минутах, цена в BYN.
Специалисты создаются отдельно и получают список slug'ов услуг.
Это примеры, которые владелец переименовывает под свой бизнес.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Product, Specialist
from app.utils import money, slugify


SERVICE_DEMO_CATALOG: dict[str, list[tuple[str, str, str, list[tuple[str, str, float, int, str]]]]] = {
    "services": [
        ("remont-uslug", "Ремонт и работы", "Выезд мастера и работы на месте", [
            ("zamena-zamka", "Замена замка", 35.00, 60, "Выезд мастера, демонтаж и установка нового замка."),
            ("sborka-mebeli", "Сборка мебели", 60.00, 120, "Сборка корпусной мебели до трёх часов."),
        ]),
        ("konsultacii-uslug", "Консультации", "Помощь специалиста по записи", [
            ("konsultaciya-uslug", "Консультация", 45.00, 45, "45 минут онлайн или в офисе."),
            ("diagnostika-uslug", "Диагностика", 25.00, 30, "Осмотр и оценка объёма работ."),
        ]),
    ],
    "hairdresser": [
        ("strizhki", "Стрижки", "Женские, мужские и детские", [
            ("zhenskaya-strizhka", "Женская стрижка", 45.00, 60, "Стрижка с укладкой и рекомендациями по уходу."),
            ("muzhskaya-strizhka", "Мужская стрижка", 30.00, 45, "Стрижка машинкой и ножницами, оформление."),
            ("detskaya-strizhka", "Детская стрижка", 25.00, 30, "Аккуратная стрижка для детей до 12 лет."),
        ]),
        ("okrashivanie", "Окрашивание", "Тон, мелирование и уход", [
            ("tonirovanie", "Тонирование", 70.00, 90, "Освежение цвета и блеск без осветления."),
            ("okrashivanie-odin-ton", "Окрашивание в один тон", 95.00, 120, "Стойкая краска и уход после окрашивания."),
        ]),
        ("uhod", "Уход", "Укладка и восстановление", [
            ("ukladka", "Укладка", 35.00, 45, "Укладка феном или стайлером на ваш выбор."),
            ("vosstanovlenie", "Восстановление волос", 55.00, 60, "Питательная маска и уход по типу волос."),
        ]),
    ],
    "barbershop": [
        ("strizhki-barber", "Стрижки", "Мужские стрижки и оформление", [
            ("muzhskaya-strizhka-barber", "Мужская стрижка", 35.00, 45, "Классическая или современная форма, укладка."),
            ("strizhka-mashinkoy", "Стрижка машинкой", 22.00, 30, "Одна насадка или плавный переход."),
            ("detskaya-strizhka-barber", "Детская стрижка", 25.00, 30, "Для детей до 12 лет, без слёз."),
        ]),
        ("boroda", "Борода", "Форма, бритьё и уход", [
            ("oformlenie-borody", "Оформление бороды", 25.00, 30, "Форма, контур и уход маслом."),
            ("britie-opasnoy", "Бритьё опасной бритвой", 30.00, 40, "Горячее полотенце и уход после бритья."),
        ]),
    ],
    "beauty": [
        ("manikyur", "Маникюр", "Ногти и покрытие", [
            ("manikyur-klassicheskiy", "Классический маникюр", 30.00, 60, "Обработка кутикулы и форма ногтей."),
            ("manikyur-apparatnyy", "Аппаратный маникюр", 40.00, 75, "Бережная обработка аппаратом."),
            ("pokrytie-gel", "Покрытие гель-лаком", 50.00, 90, "Стойкое покрытие с дизайном на выбор."),
        ]),
        ("brovi", "Брови", "Коррекция и окрашивание", [
            ("korrekciya-brovey", "Коррекция бровей", 20.00, 30, "Форма с учётом черт лица."),
            ("okrashivanie-brovey", "Окрашивание бровей", 25.00, 45, "Краска или хна, подбор оттенка."),
        ]),
        ("kosmetologiya", "Косметология", "Уход за лицом", [
            ("chistka-lica", "Чистка лица", 65.00, 60, "Глубокое очищение и уход по типу кожи."),
            ("massazh-lica", "Массаж лица", 45.00, 45, "Лимфодренажный массаж и увлажнение."),
        ]),
    ],
    "massage": [
        ("massazh", "Массаж", "Тело и восстановление", [
            ("klassicheskiy-massazh", "Классический массаж", 60.00, 60, "Общий массаж тела по вашему запросу."),
            ("rasslablyayushchiy-massazh", "Расслабляющий массаж", 80.00, 90, "Медленные техники и аромамасла."),
            ("sportivnyy-massazh", "Спортивный массаж", 70.00, 60, "Глубокие техники для восстановления."),
        ]),
        ("spa", "SPA-ритуалы", "Обёртывания и уход", [
            ("stone-terapiya", "Стоун-терапия", 90.00, 90, "Горячие камни и расслабление."),
            ("oborachivanie", "Обёртывание", 65.00, 60, "Детокс- или питательное обёртывание."),
        ]),
    ],
    "clinic": [
        ("priem-vracha", "Приём врача", "Консультации специалистов", [
            ("terapevt", "Приём терапевта", 45.00, 30, "Осмотр, план обследования и рекомендации."),
            ("pediatr", "Приём педиатра", 50.00, 30, "Осмотр ребёнка и рекомендации родителям."),
        ]),
        ("diagnostika", "Диагностика", "Обследования", [
            ("ekg", "ЭКГ", 25.00, 20, "Запись и расшифровка электрокардиограммы."),
            ("uzi", "УЗИ", 55.00, 30, "Ультразвуковое исследование по направлению."),
        ]),
        ("procedury", "Процедуры", "Лечение и манипуляции", [
            ("kapelnica", "Капельница", 40.00, 60, "Постановка системы и наблюдение."),
            ("inekciya", "Инъекция", 15.00, 15, "Внутримышечная или подкожная инъекция."),
        ]),
    ],
    "dental": [
        ("priem-stomatolog", "Приём", "Консультации и гигиена", [
            ("konsultaciya-stomatologa", "Консультация стоматолога", 30.00, 30, "Осмотр, снимок и план лечения."),
            ("gigiena-polosti-rta", "Профессиональная гигиена", 70.00, 60, "Ультразвук, полировка и фторирование."),
        ]),
        ("lechenie", "Лечение", "Терапия и каналы", [
            ("lechenie-kariesa", "Лечение кариеса", 90.00, 60, "Пломба из светового композита."),
            ("lechenie-kanalov", "Лечение каналов", 150.00, 90, "Эндодонтическое лечение под контролем."),
        ]),
        ("protezirovanie", "Протезирование", "Коронки и слепки", [
            ("slepok", "Слепок", 25.00, 30, "Снятие слепка для коронки или протеза."),
            ("kronka", "Установка коронки", 220.00, 60, "Фиксация коронки и проверка прикуса."),
        ]),
    ],
    "psychology": [
        ("konsultacii-psiholog", "Консультации", "Личная и парная работа", [
            ("individualnaya-konsultaciya", "Индивидуальная консультация", 60.00, 60, "Разбор запроса и первые шаги."),
            ("parnaya-konsultaciya", "Парная консультация", 90.00, 90, "Работа с коммуникацией в паре."),
            ("onlayn-konsultaciya", "Онлайн-консультация", 55.00, 60, "Встреча в видеосвязи из любого места."),
        ]),
    ],
    "tutoring": [
        ("zanyatiya", "Занятия", "Школьная программа", [
            ("matematika", "Математика", 35.00, 60, "Разбор тем и домашних заданий."),
            ("fizika", "Физика", 35.00, 60, "Теория и практика решения задач."),
            ("angliyskiy", "Английский язык", 35.00, 60, "Разговорная практика и грамматика."),
        ]),
        ("podgotovka", "Подготовка к экзаменам", "Интенсив и пробники", [
            ("podgotovka-ege", "Подготовка к ЦТ/ЕГЭ", 45.00, 90, "Программа и пробные тесты."),
            ("olimpiada", "Олимпиадная подготовка", 50.00, 90, "Нестандартные задачи и разборы."),
        ]),
    ],
    "fitness": [
        ("trenirovki", "Тренировки", "Персональные и групповые", [
            ("personalnaya-trenirovka", "Персональная тренировка", 45.00, 60, "Программа под вашу цель и уровень."),
            ("grupovaya-trenirovka", "Групповая тренировка", 18.00, 45, "Небольшая группа и внимание тренера."),
            ("rastyazhka", "Растяжка", 20.00, 60, "Мягкая работа с гибкостью и осанкой."),
        ]),
        ("konsultacii-fitness", "Консультации", "Питание и замеры", [
            ("konsultaciya-pitanie", "Консультация по питанию", 35.00, 45, "Разбор рациона и привычек."),
            ("zamera", "Замеры и диагностика", 15.00, 20, "Состав тела и динамика."),
        ]),
    ],
    "autoservice": [
        ("to", "Техобслуживание", "Плановые работы", [
            ("zamena-masla", "Замена масла", 35.00, 60, "Масло, фильтр и проверка уровней."),
            ("diagnostika-avto", "Компьютерная диагностика", 40.00, 45, "Считывание ошибок и рекомендации."),
            ("shinomontazh", "Шиномонтаж", 40.00, 60, "Снятие, монтаж и балансировка."),
        ]),
        ("remont-avto", "Ремонт", "Ходовая и тормоза", [
            ("remont-tormozov", "Ремонт тормозов", 70.00, 90, "Колодки, диски и проверка системы."),
            ("remont-podveski", "Ремонт подвески", 120.00, 120, "Диагностика и замена элементов."),
        ]),
    ],
    "repair": [
        ("remont-master", "Ремонт", "Мастер на дом", [
            ("santehnika", "Сантехника", 40.00, 60, "Краны, смесители, мелкий ремонт."),
            ("elektrika", "Электрика", 40.00, 60, "Розетки, освещение, поиск неисправностей."),
            ("bytovaya-tehnika", "Ремонт бытовой техники", 55.00, 90, "Диагностика и ремонт на месте."),
        ]),
        ("vyezd", "Выезд", "Оценка и консультация", [
            ("diagnostika-vyezd", "Выезд и диагностика", 20.00, 30, "Осмотр и смета работ."),
        ]),
    ],
    "cleaning": [
        ("uborka", "Уборка", "Квартиры и офисы", [
            ("standartnaya-uborka", "Стандартная уборка", 80.00, 120, "Пыль, полы, санузлы и кухня."),
            ("generalnaya-uborka", "Генеральная уборка", 150.00, 240, "Глубокая уборка всех поверхностей."),
            ("uborka-posle-remonta", "Уборка после ремонта", 190.00, 300, "Строительная пыль и следы работ."),
        ]),
        ("dop-uslugi", "Дополнительно", "Мебель и окна", [
            ("himchistka-mebeli", "Химчистка мебели", 70.00, 90, "Диван или два кресла, безопасные средства."),
            ("mytye-okon", "Мытьё окон", 50.00, 120, "Стёкла и рамы, до пяти окон."),
        ]),
    ],
    "photo": [
        ("semka", "Съёмка", "Портрет и контент", [
            ("portretnaya-semka", "Портретная съёмка", 90.00, 60, "Студия, свет и 10 обработанных кадров."),
            ("semeynaya-semka", "Семейная съёмка", 120.00, 90, "Естественные кадры для всей семьи."),
            ("predmetnaya-semka", "Предметная съёмка", 80.00, 60, "До 10 предметов для маркетплейса."),
        ]),
        ("obrabotka", "Обработка", "Ретушь и монтаж", [
            ("retush", "Ретушь фото", 40.00, 45, "Цветокоррекция и деликатная ретушь."),
        ]),
    ],
    "events": [
        ("meropriyatiya", "Мероприятия", "Праздники и события", [
            ("konsultaciya-meropriyatie", "Консультация по событию", 30.00, 30, "Формат, бюджет и план подготовки."),
            ("organizaciya-prazdnika", "Организация праздника", 150.00, 120, "Сценарий, подрядчики и координация."),
            ("dekor-meropriyatiya", "Декор мероприятия", 90.00, 90, "Оформление зоны и фотозоны."),
        ]),
    ],
    "consulting": [
        ("konsultacii-biznes", "Консультации", "Бизнес и маркетинг", [
            ("biznes-konsultaciya", "Бизнес-консультация", 80.00, 60, "Стратегия, процессы и точки роста."),
            ("finansovaya-konsultaciya", "Финансовая консультация", 80.00, 60, "Бюджет, cashflow и планирование."),
            ("marketing-konsultaciya", "Маркетинговая консультация", 75.00, 60, "Каналы, воронка и упаковка."),
        ]),
        ("audit", "Аудит", "Разбор и рекомендации", [
            ("audit-prodazh", "Аудит продаж", 140.00, 120, "Разбор воронки и план улучшений."),
        ]),
    ],
    "veterinary": [
        ("priem-vet", "Приём", "Ветеринарные услуги", [
            ("terapevt-vet", "Приём ветеринара", 40.00, 30, "Осмотр, консультация и назначения."),
            ("vakcinaciya", "Вакцинация", 30.00, 20, "Вакцина и отметка в паспорте."),
            ("stomatologiya-vet", "Стоматология", 70.00, 60, "Осмотр полости рта и чистка зубов."),
        ]),
        ("procedury-vet", "Процедуры", "Диагностика и уход", [
            ("uzi-vet", "УЗИ", 45.00, 30, "Ультразвуковое исследование животного."),
            ("grooming", "Груминг", 60.00, 90, "Стрижка, купание и уход за шерстью."),
        ]),
    ],
}


SERVICE_SPECIALISTS: dict[str, list[tuple[str, str, str, list[str]]]] = {
    "services": [
        ("master-universal", "Мастер", "Специалист по работам", []),
    ],
    "hairdresser": [
        ("anna", "Анна", "Стилист-парикмахер", ["zhenskaya-strizhka", "tonirovanie", "okrashivanie-odin-ton", "ukladka"]),
        ("marina", "Марина", "Парикмахер-колорист", ["zhenskaya-strizhka", "okrashivanie-odin-ton", "vosstanovlenie"]),
        ("dmitriy", "Дмитрий", "Мужской мастер", ["muzhskaya-strizhka", "detskaya-strizhka", "ukladka"]),
    ],
    "barbershop": [
        ("artem", "Артём", "Барбер", ["muzhskaya-strizhka-barber", "strizhka-mashinkoy", "oformlenie-borody"]),
        ("ivan", "Иван", "Барбер-стилист", ["muzhskaya-strizhka-barber", "britie-opasnoy", "oformlenie-borody"]),
    ],
    "beauty": [
        ("olga", "Ольга", "Мастер маникюра", ["manikyur-klassicheskiy", "manikyur-apparatnyy", "pokrytie-gel"]),
        ("svetlana", "Светлана", "Бровист", ["korrekciya-brovey", "okrashivanie-brovey"]),
        ("elena", "Елена", "Косметолог", ["chistka-lica", "massazh-lica"]),
    ],
    "massage": [
        ("igor", "Игорь", "Массажист", ["klassicheskiy-massazh", "sportivnyy-massazh"]),
        ("irina", "Ирина", "SPA-мастер", ["rasslablyayushchiy-massazh", "stone-terapiya", "oborachivanie"]),
    ],
    "clinic": [
        ("doctor-terapevt", "Елена Петровна", "Терапевт", ["terapevt", "ekg", "kapelnica"]),
        ("doctor-pediatr", "Ольга Сергеевна", "Педиатр", ["pediatr", "inekciya"]),
        ("doctor-uzi", "Наталья Игоревна", "Врач УЗИ", ["uzi", "ekg"]),
    ],
    "dental": [
        ("dent-therapist", "Алексей Иванович", "Стоматолог-терапевт", ["konsultaciya-stomatologa", "gigiena-polosti-rta", "lechenie-kariesa", "lechenie-kanalov"]),
        ("dent-orthoped", "Марина Павловна", "Стоматолог-ортопед", ["konsultaciya-stomatologa", "slepok", "kronka"]),
    ],
    "psychology": [
        ("psy-anna", "Анна", "Психолог", ["individualnaya-konsultaciya", "onlayn-konsultaciya"]),
        ("psy-pavel", "Павел", "Семейный психолог", ["parnaya-konsultaciya", "individualnaya-konsultaciya"]),
    ],
    "tutoring": [
        ("tutor-math", "Сергей", "Репетитор по математике", ["matematika", "podgotovka-ege", "olimpiada"]),
        ("tutor-eng", "Екатерина", "Репетитор по английскому", ["angliyskiy", "podgotovka-ege"]),
        ("tutor-phys", "Андрей", "Репетитор по физике", ["fizika", "podgotovka-ege", "olimpiada"]),
    ],
    "fitness": [
        ("trainer-alex", "Алексей", "Персональный тренер", ["personalnaya-trenirovka", "konsultaciya-pitanie", "zamera"]),
        ("trainer-yoga", "Дарья", "Инструктор по растяжке", ["rastyazhka", "grupovaya-trenirovka"]),
    ],
    "autoservice": [
        ("mechanic-sergey", "Сергей", "Автомеханик", ["zamena-masla", "remont-tormozov", "remont-podveski"]),
        ("diagnost-andrey", "Андрей", "Диагност", ["diagnostika-avto", "shinomontazh"]),
    ],
    "repair": [
        ("master-plumb", "Виктор", "Сантехник", ["santehnika", "diagnostika-vyezd"]),
        ("master-electric", "Николай", "Электрик", ["elektrika", "diagnostika-vyezd"]),
        ("master-appliance", "Павел", "Мастер по технике", ["bytovaya-tehnika", "diagnostika-vyezd"]),
    ],
    "cleaning": [
        ("cleaner-1", "Команда клининга", "Уборка квартир и офисов", []),
    ],
    "photo": [
        ("photographer-1", "Алина", "Фотограф", ["portretnaya-semka", "semeynaya-semka", "retush"]),
        ("photographer-2", "Максим", "Предметный фотограф", ["predmetnaya-semka", "retush"]),
    ],
    "events": [
        ("event-1", "Кристина", "Организатор мероприятий", ["konsultaciya-meropriyatie", "organizaciya-prazdnika", "dekor-meropriyatiya"]),
    ],
    "consulting": [
        ("consult-1", "Дмитрий", "Бизнес-консультант", ["biznes-konsultaciya", "audit-prodazh"]),
        ("consult-2", "Ирина", "Финансовый консультант", ["finansovaya-konsultaciya", "audit-prodazh"]),
        ("consult-3", "Артём", "Маркетолог", ["marketing-konsultaciya", "audit-prodazh"]),
    ],
    "veterinary": [
        ("vet-1", "Екатерина", "Ветеринарный врач", ["terapevt-vet", "vakcinaciya", "stomatologiya-vet"]),
        ("vet-2", "Ольга", "Ветеринар-грумер", ["grooming", "uzi-vet"]),
    ],
}


def seed_service_catalog(db: Session, tenant_id: int, preset: str | None) -> int:
    """Создаёт примеры услуг и специалистов. Идемпотентно по slug."""
    rows = SERVICE_DEMO_CATALOG.get(preset or "")
    if not rows:
        return 0

    created = 0
    service_ids: dict[str, int] = {}
    for order, (slug, title, description, services) in enumerate(rows):
        category = db.scalar(
            select(Category).where(
                Category.tenant_id == tenant_id, Category.slug == slug
            )
        )
        if not category:
            category = Category(
                tenant_id=tenant_id,
                slug=slug,
                title=title,
                description=description,
                sort_order=(order + 1) * 10,
                is_active=True,
            )
            db.add(category)
            db.flush()
        for index, (product_slug, product_title, price, duration, short) in enumerate(services):
            product = db.scalar(
                select(Product).where(
                    Product.tenant_id == tenant_id, Product.slug == product_slug
                )
            )
            if not product:
                product = Product(
                    tenant_id=tenant_id,
                    slug=product_slug,
                    title=product_title,
                    subtitle="",
                    category_id=category.id,
                    unit="piece",
                    kind="service",
                    duration_minutes=duration,
                    buffer_minutes=10,
                    capacity=1,
                    price=money(Decimal(str(price))),
                    discount_percent=0,
                    is_daily_deal=False,
                    is_available=True,
                    is_active=True,
                    stock=None,
                    weight_note="",
                    image_url=None,
                    gallery=[],
                    badges=[],
                    short_description=short,
                    description=short,
                    origin="",
                    season="",
                    nutrition={},
                    cooking_tips="",
                    storage_tips="",
                    sort_order=(index + 1) * 10,
                )
                db.add(product)
                db.flush()
                created += 1
            service_ids[product_slug] = product.id

    for order, (slug, name, role, service_slugs) in enumerate(
        SERVICE_SPECIALISTS.get(preset or "", [])
    ):
        existing = db.scalar(
            select(Specialist.id).where(
                Specialist.tenant_id == tenant_id, Specialist.slug == slug
            )
        )
        if existing:
            continue
        ids = [service_ids[item] for item in service_slugs if item in service_ids]
        db.add(
            Specialist(
                tenant_id=tenant_id,
                slug=slug or slugify(name, "specialist"),
                name=name,
                role=role,
                bio="",
                service_ids=ids,
                working_hours=[],
                time_off=[],
                sort_order=(order + 1) * 10,
                is_active=True,
            )
        )
    db.commit()
    return created

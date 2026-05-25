"""Маппинг имён колонок → Faker-генераторы.

Анализирует имя колонки и тип данных, чтобы выбрать
максимально реалистичный генератор.
"""

# Паттерны имён колонок → метод Faker
# Порядок важен: более специфичные паттерны идут первые
COLUMN_PATTERNS: list[tuple[list[str], str]] = [
    # Персональные данные
    (["first_name", "firstname", "fname", "given_name"], "first_name"),
    (["last_name", "lastname", "lname", "surname", "family_name"], "last_name"),
    (["middle_name", "middlename", "patronymic"], "first_name"),
    (["full_name", "fullname", "display_name", "displayname"], "name"),
    (["username", "user_name", "login", "nickname", "nick"], "user_name"),

    # Контакты
    (["email", "e_mail", "email_address", "mail"], "email"),
    (["phone", "phone_number", "telephone", "tel", "mobile", "cell"], "phone_number"),

    # Адреса
    (["country", "country_name"], "country"),
    (["country_code", "country_iso"], "country_code"),
    (["city", "town"], "city"),
    (["state", "province", "region"], "state"),
    (["street", "street_address", "address_line", "address1", "address2"], "street_address"),
    (["address", "full_address"], "address"),
    (["zip", "zipcode", "zip_code", "postal_code", "postcode"], "postcode"),
    (["latitude", "lat"], "latitude"),
    (["longitude", "lng", "lon"], "longitude"),

    # Интернет
    (["url", "website", "web", "homepage", "site_url", "link"], "url"),
    (["domain", "domain_name", "hostname"], "domain_name"),
    (["ip", "ip_address", "ipv4"], "ipv4"),
    (["ipv6"], "ipv6"),
    (["mac", "mac_address"], "mac_address"),
    (["user_agent", "useragent"], "user_agent"),
    (["slug"], "slug"),

    # Финансы
    (["price", "cost", "amount", "total", "subtotal", "sum"], "_price"),
    (["currency", "currency_code"], "currency_code"),
    (["iban"], "iban"),
    (["credit_card", "card_number", "cc_number"], "credit_card_number"),

    # Компания
    (["company", "company_name", "organization", "org"], "company"),
    (["job", "job_title", "position", "role", "occupation"], "job"),

    # Текст
    (["title", "heading", "subject", "headline"], "sentence"),
    (["description", "desc", "summary", "about", "bio", "overview"], "paragraph"),
    (["content", "body", "text", "message", "comment", "note", "notes"], "text"),

    # Даты
    (["birthday", "birthdate", "date_of_birth", "dob", "birth_date"], "_past_date"),
    (["created_at", "createdat", "created", "creation_date", "registered_at", "signup_date"], "_recent_datetime"),
    (["updated_at", "updatedat", "updated", "modified_at", "modified", "last_modified"], "_recent_datetime"),
    (["deleted_at", "deletedat"], "_recent_datetime"),
    (["published_at", "publishedat", "publish_date"], "_recent_datetime"),
    (["expires_at", "expiresat", "expiry", "expiration", "valid_until"], "_future_datetime"),
    (["start_date", "started_at", "begin_date", "from_date"], "_recent_date"),
    (["end_date", "ended_at", "finish_date", "to_date", "due_date", "deadline"], "_future_date"),

    # Файлы / медиа
    (["image", "photo", "avatar", "picture", "thumbnail", "img", "image_url", "photo_url", "avatar_url"], "_image_url"),
    (["file", "file_path", "filepath", "attachment"], "file_path"),
    (["filename", "file_name"], "file_name"),
    (["mime", "mime_type", "content_type"], "mime_type"),
    (["extension", "ext", "file_ext"], "file_extension"),

    # ID / коды
    (["uuid", "guid", "uid"], "uuid4"),
    (["color", "colour", "hex_color"], "hex_color"),
    (["locale", "lang", "language", "language_code"], "locale"),

    # Boolean-подобные
    (["is_active", "active", "enabled", "is_enabled", "is_verified", "verified"], "_true_biased"),
    (["is_deleted", "deleted", "is_archived", "archived", "is_blocked", "blocked"], "_false_biased"),

    # Пароль / хеш
    (["password", "passwd", "pass", "password_hash", "hashed_password"], "_password_hash"),
    (["token", "access_token", "refresh_token", "api_key", "secret", "secret_key"], "_token"),
    (["hash", "checksum", "md5", "sha256"], "sha256"),
]

# Маппинг SQL-типов на базовые генераторы (fallback)
TYPE_GENERATORS: dict[str, str] = {
    "integer": "_random_int",
    "bigint": "_random_bigint",
    "smallint": "_random_smallint",
    "serial": "_random_int",
    "bigserial": "_random_bigint",
    "real": "_random_float",
    "double precision": "_random_float",
    "numeric": "_random_decimal",
    "decimal": "_random_decimal",
    "boolean": "_random_bool",
    "text": "sentence",
    "character varying": "sentence",
    "varchar": "sentence",
    "char": "_random_char",
    "character": "_random_char",
    "uuid": "uuid4",
    "date": "_random_date",
    "timestamp without time zone": "_random_datetime",
    "timestamp with time zone": "_random_datetime_tz",
    "time without time zone": "_random_time",
    "time with time zone": "_random_time",
    "json": "_random_json",
    "jsonb": "_random_json",
    "inet": "ipv4",
    "cidr": "ipv4",
    "macaddr": "mac_address",
    "bytea": "_random_bytes",
    "interval": "_random_interval",
    "ARRAY": "_empty_array",
}


def match_generator(column_name: str, data_type: str) -> str:
    """Определить лучший генератор для колонки по имени и типу."""
    name_lower = column_name.lower()

    # 1. Точное совпадение с паттерном
    for patterns, generator in COLUMN_PATTERNS:
        if name_lower in patterns:
            return generator

    # 2. Частичное совпадение (содержит паттерн)
    for patterns, generator in COLUMN_PATTERNS:
        for pattern in patterns:
            if pattern in name_lower or name_lower in pattern:
                return generator

    # 3. Fallback по типу данных
    type_lower = data_type.lower()
    if type_lower in TYPE_GENERATORS:
        return TYPE_GENERATORS[type_lower]

    # 4. Проверяем частичное совпадение типа
    for type_key, gen in TYPE_GENERATORS.items():
        if type_key in type_lower:
            return gen

    # 5. Дефолт
    return "sentence"

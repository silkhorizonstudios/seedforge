"""Column name to generator mapping.

Picks the best data generator based on column name, table context,
and SQL type.
"""

# Column name patterns -> Faker method
# Order matters: more specific patterns first
COLUMN_PATTERNS: list[tuple[list[str], str]] = [
    # Personal
    (["first_name", "firstname", "fname", "given_name"], "first_name"),
    (["last_name", "lastname", "lname", "surname", "family_name"], "last_name"),
    (["middle_name", "middlename", "patronymic"], "first_name"),
    (["full_name", "fullname", "display_name", "displayname"], "name"),
    (["username", "user_name", "login", "nickname", "nick"], "user_name"),

    # Contact
    (["email", "e_mail", "email_address", "mail"], "email"),
    (["phone", "phone_number", "telephone", "tel", "mobile", "cell"], "phone_number"),

    # Address
    (["country", "country_name"], "country"),
    (["country_code", "country_iso"], "country_code"),
    (["city", "town"], "city"),
    (["state", "province", "region"], "state"),
    (["street", "street_address", "address_line", "address1", "address2"], "street_address"),
    (["address", "full_address"], "address"),
    (["zip", "zipcode", "zip_code", "postal_code", "postcode"], "postcode"),
    (["latitude", "lat"], "latitude"),
    (["longitude", "lng", "lon"], "longitude"),

    # Internet
    (["url", "website", "web", "homepage", "site_url", "link"], "url"),
    (["domain", "domain_name", "hostname"], "domain_name"),
    (["ip", "ip_address", "ipv4"], "ipv4"),
    (["ipv6"], "ipv6"),
    (["mac", "mac_address"], "mac_address"),
    (["user_agent", "useragent"], "user_agent"),
    (["slug"], "slug"),

    # Finance
    (["price", "cost", "amount", "total", "subtotal", "sum", "fee", "balance", "revenue"], "_price"),
    (["currency", "currency_code"], "currency_code"),
    (["iban"], "iban"),
    (["credit_card", "card_number", "cc_number"], "credit_card_number"),
    (["discount", "discount_percent", "tax_rate", "rate", "percent", "percentage"], "_percentage"),

    # Company
    (["company", "company_name", "organization", "org", "org_name", "business_name", "brand"], "company"),
    (["job", "job_title", "position", "occupation"], "job"),

    # Text
    (["title", "heading", "subject", "headline"], "_short_title"),
    (["name"], "_context_name"),  # context-dependent
    (["description", "desc", "summary", "about", "bio", "overview"], "paragraph"),
    (["content", "body", "text", "message", "comment", "note", "notes"], "text"),
    (["reason", "feedback"], "sentence"),

    # Roles and statuses
    (["role"], "_role"),
    (["status"], "_status"),
    (["type", "kind", "category"], "_type_field"),
    (["priority", "severity", "level"], "_priority"),
    (["plan", "tier", "subscription"], "_plan"),
    (["gender", "sex"], "_gender"),

    # Counts
    (["count", "quantity", "qty", "num", "number", "total_count", "views", "likes",
      "downloads", "rating_count", "order_count", "visit_count"], "_count"),
    (["rating", "score", "grade"], "_rating"),
    (["sort_order", "position", "order", "rank", "weight", "sequence", "seq", "priority_order"], "_sort_order"),
    (["max_employees", "max_users", "max_items", "limit", "max", "capacity"], "_capacity"),
    (["age", "min_age", "max_age"], "_age"),
    (["duration", "length", "minutes", "hours", "days"], "_duration"),
    (["width", "height", "size"], "_dimension"),

    # Dates
    (["birthday", "birthdate", "date_of_birth", "dob", "birth_date"], "_past_date"),
    (["created_at", "createdat", "created", "creation_date", "registered_at", "signup_date",
      "joined_at", "invited_at", "added_at"], "_recent_datetime"),
    (["updated_at", "updatedat", "updated", "modified_at", "modified", "last_modified"], "_recent_datetime"),
    (["deleted_at", "deletedat"], "_recent_datetime"),
    (["published_at", "publishedat", "publish_date"], "_recent_datetime"),
    (["expires_at", "expiresat", "expiry", "expiration", "valid_until",
      "premium_until", "trial_until", "subscription_until"], "_future_datetime"),
    (["start_date", "started_at", "begin_date", "from_date"], "_recent_date"),
    (["end_date", "ended_at", "finish_date", "to_date", "due_date", "deadline"], "_future_date"),
    (["last_login", "last_seen", "last_activity", "last_active"], "_recent_datetime"),

    # Files / media
    (["image", "photo", "avatar", "picture", "thumbnail", "img", "image_url",
      "photo_url", "avatar_url", "cover", "cover_url", "logo", "logo_url", "icon"], "_image_url"),
    (["file", "file_path", "filepath", "attachment"], "file_path"),
    (["filename", "file_name"], "file_name"),
    (["mime", "mime_type", "content_type"], "mime_type"),
    (["extension", "ext", "file_ext"], "file_extension"),

    # IDs / codes
    (["uuid", "guid", "uid"], "uuid4"),
    (["code", "ref_code", "reference", "ref", "sku", "barcode", "product_code"], "_code"),
    (["color", "colour", "hex_color"], "hex_color"),
    (["locale", "lang", "language", "language_code"], "locale"),
    (["google_id", "facebook_id", "apple_id", "github_id", "social_id",
      "external_id", "provider_id", "oauth_id"], "_social_id"),

    # Booleans
    (["is_active", "active", "enabled", "is_enabled", "is_verified", "verified",
      "is_published", "published", "is_visible", "visible", "is_public",
      "is_premium", "premium", "is_paid", "paid", "save_results"], "_true_biased"),
    (["is_deleted", "deleted", "is_archived", "archived", "is_blocked", "blocked",
      "is_banned", "banned", "is_spam", "spam", "is_admin", "is_superadmin"], "_false_biased"),
    (["is_template", "is_default", "is_featured", "featured"], "_false_biased"),

    # Password / hash
    (["password", "passwd", "pass", "password_hash", "hashed_password"], "_password_hash"),
    (["token", "access_token", "refresh_token", "api_key", "secret", "secret_key"], "_token"),
    (["hash", "checksum", "md5", "sha256"], "sha256"),

    # Arrays (JSONB/JSON)
    (["test_ids", "user_ids", "item_ids", "tags", "labels", "categories", "permissions"], "_id_array"),
]

# SQL type -> generator fallback
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

# Table name context for the "name" column
TABLE_NAME_CONTEXT: dict[str, str] = {
    "organizations": "company",
    "organisation": "company",
    "companies": "company",
    "company": "company",
    "brands": "company",
    "shops": "company",
    "stores": "company",
    "vendors": "company",
    "suppliers": "company",
    "clients": "company",
    "partners": "company",
    "products": "_product_name",
    "items": "_product_name",
    "goods": "_product_name",
    "services": "_service_name",
    "categories": "_category_name",
    "tags": "word",
    "labels": "word",
    "users": "name",
    "profiles": "name",
    "employees": "name",
    "staff": "name",
    "members": "name",
    "customers": "name",
    "contacts": "name",
    "authors": "name",
    "countries": "country",
    "cities": "city",
    "departments": "_department_name",
    "teams": "_team_name",
    "projects": "_project_name",
    "tasks": "_short_title",
    "tickets": "_short_title",
    "issues": "_short_title",
    "events": "_event_name",
    "courses": "_course_name",
    "tests": "_test_name",
    "exams": "_test_name",
    "rooms": "_room_name",
    "plans": "_plan",
    "roles": "_role",
}


def match_generator(column_name: str, data_type: str, table_name: str = "") -> str:
    """Pick the best generator for a column."""
    name_lower = column_name.lower()

    # 1. Exact match
    for patterns, generator in COLUMN_PATTERNS:
        if name_lower in patterns:
            # "name" is context-dependent
            if generator == "_context_name" and table_name:
                return _resolve_context_name(table_name)
            return generator

    # 2. Partial match
    for patterns, generator in COLUMN_PATTERNS:
        for pattern in patterns:
            if len(pattern) >= 3 and (pattern in name_lower or name_lower in pattern):
                return generator

    # 3. Fallback by SQL type
    type_lower = data_type.lower()
    if type_lower in TYPE_GENERATORS:
        return TYPE_GENERATORS[type_lower]

    # 4. Partial type match
    for type_key, gen in TYPE_GENERATORS.items():
        if type_key in type_lower:
            return gen

    # 5. Default
    return "sentence"


def _resolve_context_name(table_name: str) -> str:
    """Resolve generator for the 'name' column based on table context."""
    tbl = table_name.lower()
    if tbl in TABLE_NAME_CONTEXT:
        return TABLE_NAME_CONTEXT[tbl]
    # Check partial match
    for key, gen in TABLE_NAME_CONTEXT.items():
        if key in tbl or tbl in key:
            return gen
    return "_short_title"

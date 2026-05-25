"""Тесты для маппинга колонок → генераторы."""

from seedforge.heuristics import match_generator


class TestExactMatch:
    def test_email(self):
        assert match_generator("email", "text") == "email"

    def test_phone(self):
        assert match_generator("phone", "text") == "phone_number"

    def test_first_name(self):
        assert match_generator("first_name", "text") == "first_name"

    def test_password(self):
        assert match_generator("password", "text") == "_password_hash"

    def test_created_at(self):
        assert match_generator("created_at", "timestamp without time zone") == "_recent_datetime"

    def test_is_active(self):
        assert match_generator("is_active", "boolean") == "_true_biased"

    def test_is_deleted(self):
        assert match_generator("is_deleted", "boolean") == "_false_biased"

    def test_price(self):
        assert match_generator("price", "numeric") == "_price"

    def test_avatar_url(self):
        assert match_generator("avatar_url", "text") == "_image_url"

    def test_slug(self):
        assert match_generator("slug", "text") == "slug"

    def test_role(self):
        assert match_generator("role", "text") == "_role"

    def test_status(self):
        assert match_generator("status", "text") == "_status"

    def test_plan(self):
        assert match_generator("plan", "text") == "_plan"


class TestContextName:
    def test_name_in_organizations(self):
        result = match_generator("name", "text", "organizations")
        assert result == "company"

    def test_name_in_users(self):
        result = match_generator("name", "text", "users")
        assert result == "name"

    def test_name_in_products(self):
        result = match_generator("name", "text", "products")
        assert result == "_product_name"

    def test_name_in_categories(self):
        result = match_generator("name", "text", "categories")
        assert result == "_category_name"

    def test_name_in_unknown_table(self):
        result = match_generator("name", "text", "xyz_unknown")
        assert result == "_short_title"


class TestTypeFallback:
    def test_integer(self):
        assert match_generator("some_unknown_col", "integer") == "_random_int"

    def test_boolean(self):
        assert match_generator("some_flag", "boolean") == "_random_bool"

    def test_uuid(self):
        assert match_generator("some_id", "uuid") == "uuid4"

    def test_json(self):
        assert match_generator("metadata", "jsonb") == "_random_json"

    def test_text_fallback(self):
        assert match_generator("xyz_unknown", "text") == "sentence"


class TestPartialMatch:
    def test_user_email(self):
        assert match_generator("user_email", "text") == "email"

    def test_phone_number(self):
        assert match_generator("phone_number", "text") == "phone_number"

    def test_updated_at(self):
        assert match_generator("updated_at", "timestamp with time zone") == "_recent_datetime"

    def test_company_name(self):
        assert match_generator("company_name", "text") == "company"

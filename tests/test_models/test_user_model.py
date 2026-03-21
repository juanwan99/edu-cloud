import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole


class TestUserModel:
    def test_user_has_required_fields(self):
        columns = {c.name for c in User.__table__.columns}
        assert "username" in columns
        assert "display_name" in columns
        assert "hashed_password" in columns
        assert "is_active" in columns
        assert "phone" in columns
        assert "email" in columns

    def test_user_table_name(self):
        assert User.__tablename__ == "users"

    def test_username_unique_constraint(self):
        username_col = User.__table__.c.username
        assert username_col.unique is True

    def test_username_not_nullable(self):
        username_col = User.__table__.c.username
        assert username_col.nullable is False

    def test_set_and_verify_password(self):
        user = User(username="test", display_name="Test", hashed_password="")
        user.set_password("secret123")
        assert user.verify_password("secret123") is True
        assert user.verify_password("wrong") is False

    def test_verify_password_empty_hash(self):
        user = User(username="test", display_name="Test", hashed_password="")
        assert user.verify_password("anything") is False


class TestUserRoleModel:
    def test_user_role_has_scope_fields(self):
        columns = {c.name for c in UserRole.__table__.columns}
        assert "user_id" in columns
        assert "role" in columns
        assert "school_id" in columns
        assert "grade_ids" in columns
        assert "class_ids" in columns
        assert "subject_codes" in columns
        assert "is_primary" in columns

    def test_user_role_table_name(self):
        assert UserRole.__tablename__ == "user_roles"

    def test_user_id_not_nullable(self):
        user_id_col = UserRole.__table__.c.user_id
        assert user_id_col.nullable is False

    def test_role_not_nullable(self):
        role_col = UserRole.__table__.c.role
        assert role_col.nullable is False

    def test_school_id_nullable(self):
        school_id_col = UserRole.__table__.c.school_id
        assert school_id_col.nullable is True

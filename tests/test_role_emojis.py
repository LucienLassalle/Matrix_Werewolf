"""Tests des emojis par role."""

from roles import RoleFactory


def test_each_role_defines_emoji():
    for role_type in RoleFactory.get_available_roles():
        role = RoleFactory.create_role(role_type)
        emoji = role.__class__.__dict__.get("emoji")
        assert isinstance(emoji, str)
        assert emoji.strip()

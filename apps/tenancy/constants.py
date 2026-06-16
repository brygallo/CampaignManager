"""Static data for the tenancy app.

Plain, side-effect-free values only (mirrors sim's ``constants.py`` convention):
no logic lives here. Currently the only shared constant is the character set
allowed in a PostgreSQL schema name, used by the slug -> schema normalization.
"""

# Characters allowed in a PostgreSQL schema name derived from a tenant slug.
SAFE_SCHEMA_NAME_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_")

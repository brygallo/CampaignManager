"""Static configuration values for the authentication app.

Plain, side-effect-free data only (sim's ``constants.py`` convention): the
"remember me" cookie lifetime and the permission string that gates full
self-service profile editing (shared by the view and the profile form). No
business logic lives here.
"""

# "Mantenerme conectado por 30 días" cookie lifetime, in seconds. When the
# checkbox is checked the session cookie is extended to this age; otherwise it
# is tied to the browser session.
REMEMBER_ME_AGE_SECONDS = 30 * 24 * 60 * 60  # 30 días

# Permission that unlocks full self-service profile editing (email, phone,
# bio) in ``MyProfileEditForm`` and ``profile_view``. Without it the user can
# only edit the minimum descriptive fields (name, alias, avatar).
CHANGE_FULL_OWN_PROFILE_PERM = "authentication.change_full_own_profile"

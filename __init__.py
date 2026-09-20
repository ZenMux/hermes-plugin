"""Filesystem entry point for Hermes model-provider discovery."""

if __package__:
    from .zenmux_hermes_plugin import register
else:
    # Pytest imports a repository-root ``__init__.py`` without package context.
    from zenmux_hermes_plugin import register

register()

from django.conf import settings
from django.db import connections


class ReadReplicaRouter:
    """Use an optional replica only for opted-in reads outside transactions."""

    def db_for_read(self, model, **hints):
        if 'replica' not in connections.databases:
            return None
        if model._meta.app_label not in getattr(settings, 'READ_REPLICA_APPS', set()):
            return None
        if connections['default'].in_atomic_block:
            return None

        instance = hints.get('instance')
        if instance is not None and instance._state.db == 'default':
            return None
        return 'replica'

    def db_for_write(self, model, **hints):
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, **hints):
        if db == 'replica':
            return False
        return None
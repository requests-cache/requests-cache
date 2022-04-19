from datetime import datetime

from attr import Factory


class RichMixin:
    """Mixin that customizes output when pretty-printed with rich. Compared to default rich behavior
    for attrs classes, this does the following:

    * Inform rich about all default values so they will be excluded from output
    * Handle default value factories
    * Stringify datetime objects
    * Does not currently handle positional-only args (since we don't currently have any)
    """

    def __rich_repr__(self):
        public_attrs = [a for a in self.__attrs_attrs__ if a.repr]
        for a in public_attrs:
            default = a.default.factory() if isinstance(a.default, Factory) else a.default
            value = getattr(self, a.name)
            value = str(value) if isinstance(value, datetime) else value
            yield a.name, value, default

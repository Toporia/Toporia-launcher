# core/registry.py — find plugins by scanning a package.
#
# A plugin is any class defined in the scanned package that subclasses the
# registry's base class and sets a non-empty `name`.  There is no decorator and
# no list to maintain: adding a file to toporia/library/methods/ IS registering
# a method.  Modules whose name starts with an underscore are skipped, so shared
# helpers can live next to the plugins.
#
# The package is given by its dotted name and only imported on the first
# lookup, so core never imports the library when core itself is imported.

import importlib
import inspect
import pkgutil


class Registry:
    """A lazily discovered, name-indexed set of plugin classes.

    Plugin classes may define:
      name    : registry key (required; an empty name means "abstract, skip me")
      aliases : extra accepted names, e.g. for configs written before a rename
      order   : menu position, lower first (default 100); ties sort by name
    """

    def __init__(self, kind, base, package):
        self.kind = kind          # "method", "filter", ... — used in messages
        self.base = base
        self.package = package
        self._by_name = None      # canonical name -> class, filled on first use
        self._aliases = None      # alias -> canonical name

    def _discover(self):
        if self._by_name is not None:
            return
        by_name = {}
        package = importlib.import_module(self.package)
        for info in pkgutil.iter_modules(package.__path__):
            if info.name.startswith("_"):
                continue
            module = importlib.import_module(f"{self.package}.{info.name}")
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if (cls.__module__ == module.__name__ and issubclass(cls, self.base)
                        and cls is not self.base and getattr(cls, "name", "")):
                    other = by_name.get(cls.name)
                    if other is not None and other is not cls:
                        raise RuntimeError(
                            f"Two {self.kind}s are named {cls.name!r}: "
                            f"{other.__module__}.{other.__name__} and {cls.__module__}.{cls.__name__}"
                        )
                    by_name[cls.name] = cls
        aliases = {alias: cls.name for cls in by_name.values() for alias in getattr(cls, "aliases", ())}
        self._by_name, self._aliases = by_name, aliases

    def register(self, cls):
        """Add a plugin class by hand — from a notebook, a script or a test — and return it.

        Usable as a decorator.  The class must subclass the registry's base and
        have a name no other plugin uses.
        """
        self._discover()
        if not (isinstance(cls, type) and issubclass(cls, self.base) and getattr(cls, "name", "")):
            raise TypeError(f"A {self.kind} must subclass {self.base.__name__} and set a non-empty name")
        other = self._by_name.get(cls.name)
        if other is not None and other is not cls:
            raise RuntimeError(f"Two {self.kind}s are named {cls.name!r}: "
                               f"{other.__module__}.{other.__name__} and {cls.__module__}.{cls.__name__}")
        self._by_name[cls.name] = cls
        for alias in getattr(cls, "aliases", ()):
            self._aliases[alias] = cls.name
        return cls

    def unregister(self, name):
        """Remove a plugin added with register()."""
        self._discover()
        cls = self._by_name.pop(name)
        for alias in getattr(cls, "aliases", ()):
            self._aliases.pop(alias, None)

    def classes(self):
        """All registered classes, in menu order."""
        self._discover()
        return sorted(self._by_name.values(), key=lambda c: (getattr(c, "order", 100), c.name))

    def names(self):
        """All canonical names, in menu order."""
        return [cls.name for cls in self.classes()]

    def get(self, name):
        """Return the class registered under `name` (case-insensitive, aliases accepted)."""
        self._discover()
        key = str(name).lower()
        key = self._aliases.get(key, key)
        try:
            return self._by_name[key]
        except KeyError:
            raise ValueError(f"Unknown {self.kind} {name!r}. Available: {self.names()}") from None

    def __contains__(self, name):
        try:
            self.get(name)
        except ValueError:
            return False
        return True

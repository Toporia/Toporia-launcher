# framework/registry.py — find plugins: in Toporia's own packages, and in installed ones.
#
# A plugin is a class that subclasses the registry's base class and sets a
# non-empty `name`.  There is no decorator and no list to maintain.  Plugins
# come from three places:
#
#   1. Toporia's own package, scanned: adding a file to toporia/plugins/methods/
#      IS registering a method.  Modules starting with an underscore are skipped,
#      so shared helpers can live next to the plugins.
#   2. Other installed packages, through a standard Python entry point.  A
#      package declares, in its pyproject.toml,
#
#          [project.entry-points."toporia.updaters"]
#          my_optimiser = "my_package.optimisers"          # a module, or
#          my_other     = "my_package.optimisers:MyClass"  # one class
#
#      and after `pip install my_package` its plugins appear in the menus,
#      the CLI and the configs, without touching Toporia.  The groups are
#      toporia.methods, toporia.models, toporia.updaters, toporia.filters,
#      toporia.interpolations and toporia.responses.
#   3. By hand, with register() — from a notebook, a script or a test.
#
# A plugin that fails to import does not take the others down with it: the
# failure is kept in `errors`, shown by `toporia list` and in the GUI's log,
# and every other plugin still loads.
#
# A plugin that needs an optional package declares it, e.g.
# `dependencies = ("pymoto",)`; missing_dependencies() says which are absent,
# so menus can grey the plugin out and a run can refuse it with an install hint
# instead of failing part-way.
#
# Discovery happens on the first lookup, so core never imports the library
# when core itself is imported.

import importlib
import importlib.metadata
import importlib.util
import inspect
import pkgutil

#: Shown as a plugin's source when it comes from Toporia itself.
BUILT_IN = "toporia"


def missing_dependencies(cls):
    """The packages a plugin declares in `dependencies` that cannot be imported here.

    For a method composed of a model and an updater, both parts' dependencies count.
    """
    declared = list(getattr(cls, "dependencies", ()))
    for part in ("model", "updater"):
        declared += list(getattr(getattr(cls, part, None), "dependencies", ()))
    missing = []
    for name in dict.fromkeys(declared):
        try:
            found = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append(name)
    return missing


def install_hint(missing):
    """How to install missing dependencies, as one line."""
    return f"pip install {' '.join(missing)}"


def _entry_points(group):
    return importlib.metadata.entry_points(group=group)


class Registry:
    """A lazily discovered, name-indexed set of plugin classes.

    Plugin classes may define:
      name         : registry key (required; an empty name means "abstract, skip me")
      aliases      : extra accepted names, e.g. for configs written before a rename
      order        : menu position, lower first (default 100); ties sort by name
      dependencies : import names of optional packages it needs, e.g. ("pymoto",)
    """

    def __init__(self, kind, base, package, group=None):
        self.kind = kind          # "method", "filter", ... — used in messages
        self.base = base
        self.package = package
        self.group = group or f"toporia.{kind}s"   # the entry-point group
        self._by_name = None      # canonical name -> class, filled on first use
        self._aliases = None      # alias -> canonical name
        self._sources = {}        # canonical name -> where it came from
        self._errors = []         # (where, message) for every plugin that failed to load

    # ── Discovery ─────────────────────────────────────────────────────────────

    def _discover(self):
        if self._by_name is not None:
            return
        self._by_name, self._aliases, self._sources, self._errors = {}, {}, {}, []

        package = importlib.import_module(self.package)
        for info in pkgutil.iter_modules(package.__path__):
            if info.name.startswith("_"):
                continue
            where = f"{self.package}.{info.name}"
            try:
                module = importlib.import_module(where)
            except Exception as error:  # noqa: BLE001 — one broken plugin must not hide the rest
                self._errors.append((where, f"{type(error).__name__}: {error}"))
                continue
            for cls in self._defined_in(module):
                self._add(cls, BUILT_IN, strict=True)

        for entry_point in _entry_points(self.group):
            where = f"{entry_point.name} = {entry_point.value}"
            source = entry_point.dist.name if getattr(entry_point, "dist", None) else entry_point.value
            try:
                loaded = entry_point.load()
            except Exception as error:  # noqa: BLE001
                self._errors.append((where, f"{type(error).__name__}: {error}"))
                continue
            classes = [loaded] if isinstance(loaded, type) else self._defined_in(loaded)
            if not classes:
                self._errors.append((where, f"defines no {self.kind} (no subclass of "
                                           f"{self.base.__name__} with a name)"))
            for cls in classes:
                try:
                    self._add(cls, source, strict=False)
                except (TypeError, RuntimeError) as error:
                    self._errors.append((where, str(error)))

    @property
    def errors(self):
        """[(where, message)] for every plugin that failed to load; discovers plugins first."""
        self._discover()
        return list(self._errors)

    def _defined_in(self, module):
        return [cls for _, cls in inspect.getmembers(module, inspect.isclass)
                if cls.__module__ == module.__name__ and issubclass(cls, self.base)
                and cls is not self.base and getattr(cls, "name", "")]

    def _add(self, cls, source, strict):
        if not (isinstance(cls, type) and issubclass(cls, self.base) and getattr(cls, "name", "")):
            raise TypeError(f"{cls!r} is not a {self.kind}: it must subclass "
                            f"{self.base.__name__} and set a non-empty name")
        other = self._by_name.get(cls.name)
        if other is not None and other is not cls:
            message = (f"Two {self.kind}s are named {cls.name!r}: "
                       f"{other.__module__}.{other.__name__} and {cls.__module__}.{cls.__name__}")
            if strict:
                raise RuntimeError(message)
            raise RuntimeError(message + f"; keeping the one from {self._sources[cls.name]}")
        self._by_name[cls.name] = cls
        self._sources[cls.name] = source
        for alias in getattr(cls, "aliases", ()):
            self._aliases[alias] = cls.name

    # ── By hand ───────────────────────────────────────────────────────────────

    def register(self, cls):
        """Add a plugin class by hand — from a notebook, a script or a test — and return it.

        Usable as a decorator.  The class must subclass the registry's base and
        have a name no other plugin uses.
        """
        self._discover()
        self._add(cls, f"registered by hand ({cls.__module__})", strict=True)
        return cls

    def unregister(self, name):
        """Remove a plugin added with register()."""
        self._discover()
        cls = self._by_name.pop(name)
        self._sources.pop(name, None)
        for alias in getattr(cls, "aliases", ()):
            self._aliases.pop(alias, None)

    # ── Lookup ────────────────────────────────────────────────────────────────

    def classes(self):
        """All registered classes, in menu order."""
        self._discover()
        return sorted(self._by_name.values(), key=lambda c: (getattr(c, "order", 100), c.name))

    def names(self):
        """All canonical names, in menu order."""
        return [cls.name for cls in self.classes()]

    def source(self, name):
        """Where a plugin came from: "toporia", an installed package's name, or "registered by hand"."""
        self._discover()
        return self._sources.get(self.get(name).name, BUILT_IN)

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

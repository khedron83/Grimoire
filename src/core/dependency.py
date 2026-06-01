"""Dependency resolution from on-disk addon manifests."""

from __future__ import annotations

from collections import deque
from typing import Optional

from .addon import Addon


class DependencyError(Exception):
    pass


def missing_dependencies(addon: Addon, installed: dict[str, Addon]) -> list[str]:
    """Return dependency names from addon.depends_on that aren't in installed."""
    return [d for d in addon.depends_on if d not in installed]


def install_order(addons: list[Addon]) -> list[Addon]:
    """
    Return addons sorted so that dependencies come before dependents.
    Raises DependencyError on cycles.
    """
    by_name = {a.name: a for a in addons}
    in_degree: dict[str, int] = {a.name: 0 for a in addons}
    dependents: dict[str, list[str]] = {a.name: [] for a in addons}

    for addon in addons:
        for dep in addon.depends_on:
            if dep in by_name:
                in_degree[addon.name] += 1
                dependents[dep].append(addon.name)

    queue = deque(name for name, deg in in_degree.items() if deg == 0)
    order = []
    while queue:
        name = queue.popleft()
        order.append(by_name[name])
        for dependent in dependents[name]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(order) != len(addons):
        cycle = [a.name for a in addons if a.name not in {o.name for o in order}]
        raise DependencyError(f"Circular dependency detected: {cycle}")

    return order


def resolve_install_set(
    requested: list[Addon],
    already_installed: dict[str, Addon],
    all_available: dict[str, Addon],
) -> list[Addon]:
    """
    Given a list of addons to install, return the full set (including transitive
    dependencies) that needs to be installed, in dependency order.
    """
    to_install: dict[str, Addon] = {}
    queue = deque(requested)

    while queue:
        addon = queue.popleft()
        if addon.name in already_installed or addon.name in to_install:
            continue
        to_install[addon.name] = addon
        for dep_name in addon.depends_on:
            if dep_name in already_installed or dep_name in to_install:
                continue
            dep = all_available.get(dep_name)
            if dep is None:
                raise DependencyError(
                    f"Missing dependency '{dep_name}' required by '{addon.name}'"
                )
            queue.append(dep)

    return install_order(list(to_install.values()))

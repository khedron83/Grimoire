use std::collections::{HashMap, HashSet, VecDeque};
use crate::core::esoui::RemoteAddon;

pub fn resolve_deps(
    root: &RemoteAddon,
    available: &HashMap<String, RemoteAddon>,
    installed_dirs: &HashSet<String>,
) -> Vec<RemoteAddon> {
    let mut queue = VecDeque::new();
    queue.push_back(root.clone());
    let mut seen: HashSet<u32> = HashSet::new();
    let mut result = Vec::new();

    while let Some(addon) = queue.pop_front() {
        if seen.contains(&addon.addon_id) {
            continue;
        }
        // Skip if all dirs already on disk
        if !addon.dirs.is_empty() && addon.dirs.iter().all(|d| installed_dirs.contains(d)) {
            seen.insert(addon.addon_id);
            continue;
        }
        seen.insert(addon.addon_id);
        result.push(addon.clone());
    }
    result
}

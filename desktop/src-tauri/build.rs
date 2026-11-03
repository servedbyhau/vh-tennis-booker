fn main() {
    // Naming the app's commands gives each a permission, which capabilities/updates.json grants
    // to the backend's page; a remote page reaches no command without one.
    let commands = tauri_build::AppManifest::new().commands(&["update_version", "install_update"]);
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(commands))
        .expect("the Tauri build step failed");
}

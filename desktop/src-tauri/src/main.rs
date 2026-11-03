//! The desktop window: it starts the packaged backend, then shows the page the backend serves.
//!
//! The backend listens on one fixed port and the app is one window, so a backend that already
//! answers is used as it is, and only a backend started here is stopped on leaving. The page
//! may call two commands, to find and install a newer version (capabilities/updates.json).

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::thread;

use court_booker_desktop::{backend_answers, backend_idle, Backend, ADDRESS, ENGINE, PAGE};
use tauri::{AppHandle, Manager, RunEvent, Url, WebviewWindow};
use tauri_plugin_updater::UpdaterExt;

/// Return whether the backend is up, started here if none answers yet.
fn ensure_backend(app: &AppHandle) -> bool {
    if backend_answers(ADDRESS) {
        return true;
    }
    let Ok(folder) = app.path().resource_dir() else {
        return false;
    };
    let backend = app.state::<Backend>();
    backend.start(&folder.join(ENGINE)).is_ok() && backend.wait_until_ready(ADDRESS)
}

/// Move the waiting page on to the backend's page, or have it tell the backend did not start.
fn show_app(window: &WebviewWindow, ready: bool) {
    let shown = match (ready, Url::parse(PAGE)) {
        (true, Ok(page)) => window.navigate(page),
        _ => window.eval("showFailure()"),
    };
    if let Err(error) = shown {
        eprintln!("The window could not show the app: {error}");
    }
}

/// Return the newer version on the newest release page, if there is one.
#[tauri::command]
async fn update_version(app: AppHandle) -> Result<Option<String>, String> {
    let updater = app.updater().map_err(|error| error.to_string())?;
    let update = updater.check().await.map_err(|error| error.to_string())?;
    Ok(update.map(|update| update.version))
}

/// Download and install the newer version, then start it again.
///
/// Refused while a run holds the lock: the installer replaces the files the run uses. The
/// backend started here is stopped first for the same reason; the new window starts its own.
#[tauri::command]
async fn install_update(app: AppHandle) -> Result<(), String> {
    if !backend_idle(ADDRESS) {
        return Err("A run is going on; update once it ends".to_string());
    }
    let handle = app.clone();
    let updater = app
        .updater_builder()
        .on_before_exit(move || handle.state::<Backend>().stop())
        .build()
        .map_err(|error| error.to_string())?;
    let update = updater
        .check()
        .await
        .map_err(|error| error.to_string())?
        .ok_or_else(|| "No newer version".to_string())?;
    update
        .download_and_install(|_, _| {}, || {})
        .await
        .map_err(|error| error.to_string())
}

fn main() {
    tauri::Builder::default()
        // First, as the plugin asks: a second start only brings this window back.
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Backend::default())
        .invoke_handler(tauri::generate_handler![update_version, install_update])
        .setup(|app| {
            let handle = app.handle().clone();
            // The window shows the waiting page meanwhile.
            thread::spawn(move || {
                let ready = ensure_backend(&handle);
                if let Some(window) = handle.get_webview_window("main") {
                    show_app(&window, ready);
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("the window could not be built")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                app.state::<Backend>().stop();
            }
        });
}

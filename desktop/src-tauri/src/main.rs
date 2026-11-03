//! The desktop window: it starts the packaged backend, then shows the page the backend serves.
//!
//! The backend listens on one fixed port and the app is one window, so a backend that already
//! answers is used as it is, and only a backend started here is stopped on leaving.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::thread;

use court_booker_desktop::{backend_answers, Backend, ADDRESS, ENGINE, PAGE};
use tauri::{AppHandle, Manager, RunEvent, Url, WebviewWindow};

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

fn main() {
    tauri::Builder::default()
        // First, as the plugin asks: a second start only brings this window back.
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .manage(Backend::default())
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

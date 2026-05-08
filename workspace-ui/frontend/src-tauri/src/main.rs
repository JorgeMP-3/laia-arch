// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;

use tauri::{
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager,
};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::default().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            commands::get_config,
            commands::set_config,
            commands::set_always_on_top,
        ])
        .setup(|app| {
            // System tray
            let tray = TrayIconBuilder::new()
                .tooltip("LAIA")
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                })
                .build(app)?;

            // Tray menu (right-click)
            let menu = tauri::menu::MenuBuilder::new(app)
                .text("show", "Abrir LAIA")
                .text("new_session", "Nueva sesión")
                .separator()
                .text("quit", "Salir")
                .build()?;
            tray.set_menu(Some(menu))?;

            let app_handle = app.handle().clone();
            tray.on_menu_event(move |_tray, event| match event.id().as_ref() {
                "show" | "new_session" => {
                    if let Some(win) = app_handle.get_webview_window("main") {
                        let _ = win.show();
                        let _ = win.set_focus();
                    }
                }
                "quit" => {
                    app_handle.exit(0);
                }
                _ => {}
            });

            // Global shortcut ⌘+Shift+L — toggle window
            let app_handle2 = app.handle().clone();
            app.global_shortcut()
                .on_shortcut("CommandOrControl+Shift+L", move |_app, _shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        if let Some(win) = app_handle2.get_webview_window("main") {
                            let visible = win.is_visible().unwrap_or(false);
                            if visible {
                                let _ = win.hide();
                            } else {
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
                    }
                })?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

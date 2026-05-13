use serde::{Deserialize, Serialize};
use tauri::AppHandle;
use tauri_plugin_store::StoreExt;

const STORE_FILE: &str = "laia-config.json";

#[derive(Serialize, Deserialize, Clone, Default)]
pub struct AppConfig {
    pub server_url: String,
    pub role: String,
}

#[tauri::command]
pub fn get_config(app: AppHandle) -> AppConfig {
    let store = app.store(STORE_FILE).unwrap_or_else(|_| {
        app.store(STORE_FILE).expect("failed to open store")
    });
    AppConfig {
        server_url: store
            .get("server_url")
            .and_then(|v| v.as_str().map(String::from))
            .unwrap_or_default(),
        role: store
            .get("role")
            .and_then(|v| v.as_str().map(String::from))
            .unwrap_or_else(|| "admin".to_string()),
    }
}

#[tauri::command]
pub fn set_config(app: AppHandle, config: AppConfig) -> Result<(), String> {
    let store = app.store(STORE_FILE).map_err(|e| e.to_string())?;
    store.set("server_url", serde_json::json!(config.server_url));
    store.set("role", serde_json::json!(config.role));
    store.save().map_err(|e| e.to_string())
}

#[tauri::command]
pub fn set_always_on_top(window: tauri::WebviewWindow, value: bool) -> Result<(), String> {
    window.set_always_on_top(value).map_err(|e| e.to_string())
}

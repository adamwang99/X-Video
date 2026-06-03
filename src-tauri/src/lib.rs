use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            tauri::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::App("index.html".into()),
            )
            .title("X-Video Studio — AI World")
            .inner_size(1440.0, 900.0)
            .min_inner_size(1024.0, 700.0)
            .resizable(true)
            .fullscreen(false)
            .build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error running X-Video");
}

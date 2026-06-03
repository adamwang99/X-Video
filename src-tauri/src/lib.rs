use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            // Create main window
            let window = tauri::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::App("index.html".into()),
            )
            .title("X-Video Studio")
            .inner_size(1440.0, 900.0)
            .min_inner_size(1024.0, 700.0)
            .resizable(true)
            .fullscreen(false)
            .build()?;

            // Window customization
            window.set_title("X-Video Studio — AI World").ok();

            // Spawn Python backend server as sidecar
            let app_handle = app.handle().clone();
            std::thread::spawn(move || {
                use tauri_plugin_shell::ShellExt;
                
                // Paths to try
                let python_paths = vec![
                    "python3",
                    "/usr/local/bin/python3",
                    "/opt/homebrew/bin/python3",
                    "/usr/bin/python3",
                    "python",
                ];

                // Find Python
                let mut python_cmd = String::from("python3");
                for p in &python_paths {
                    if std::process::Command::new(p)
                        .arg("--version")
                        .output()
                        .is_ok()
                    {
                        python_cmd = p.to_string();
                        break;
                    }
                }

                // Get backend path
                let backend_dir = app_handle
                    .path()
                    .resource_dir()
                    .unwrap_or_default()
                    .join("backend");

                if !backend_dir.join("server.py").exists() {
                    // Fallback to dev path
                    let dev_path = std::env::current_dir().unwrap_or_default();
                    let dev_backend = dev_path.join("backend").join("server.py");
                    if dev_backend.exists() {
                        let shell = app_handle.shell();
                        let output = shell
                            .command(&python_cmd)
                            .args(["-u", "backend/server.py"])
                            .env("PYTHONUNBUFFERED", "1")
                            .current_dir(&dev_path)
                            .output()
                            .expect("Failed to start backend");
                        let _ = output;
                    }
                } else {
                    let shell = app_handle.shell();
                    let output = shell
                        .command(&python_cmd)
                        .args(["-u", "backend/server.py"])
                        .env("PYTHONUNBUFFERED", "1")
                        .current_dir(&backend_dir.parent().unwrap_or(&backend_dir))
                        .output()
                        .expect("Failed to start backend");
                    let _ = output;
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

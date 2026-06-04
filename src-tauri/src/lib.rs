use std::net::TcpStream;
use std::process::Command;
use std::time::Duration;
use tauri::Manager;

/// Sanitize CLI args — block potential injection
fn sanitize_args(argv: Vec<String>) {
    for arg in &argv {
        if arg.contains("&&") || arg.contains(";;") || arg.contains("$(") || arg.contains("`") {
            eprintln!("Blocked suspicious arg: {}", arg);
            std::process::exit(1);
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, argv, _cwd| {
            sanitize_args(argv);
            // Focus existing window instead of opening new one
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .setup(|app| {
            let handle = app.handle().clone();
            let res_dir = handle.path().resource_dir().expect("resource dir");
            let backend_path = res_dir.join("backend").join("server.py");

            let already_running = TcpStream::connect_timeout(
                &"127.0.0.1:8767".parse().unwrap(),
                Duration::from_millis(500),
            ).is_ok();

            if !already_running {
                let _child = if backend_path.exists() {
                    Command::new("python3")
                        .args(["-u", backend_path.to_str().unwrap()])
                        .current_dir(&res_dir)
                        .spawn()
                        .ok()
                } else {
                    Command::new("python3")
                        .args(["-u", "backend/server.py"])
                        .spawn()
                        .ok()
                };
                if _child.is_some() {
                    println!("✅ Backend started");
                }
            }

            for i in 0..20 {
                if TcpStream::connect_timeout(
                    &"127.0.0.1:8767".parse().unwrap(),
                    Duration::from_secs(1),
                ).is_ok() {
                    println!("✅ Server ready after {}s", i + 1);
                    break;
                }
                std::thread::sleep(Duration::from_secs(1));
            }

            tauri::WebviewWindowBuilder::new(
                &handle,
                "main",
                tauri::WebviewUrl::External("http://localhost:8767".parse().unwrap()),
            )
            .title("X-Video Studio — AI World")
            .inner_size(1440.0, 900.0)
            .min_inner_size(1024.0, 700.0)
            .resizable(true)
            .center()
            .build()?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error running X-Video");
}

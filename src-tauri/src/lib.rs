use std::net::TcpStream;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;

struct BackendProcess(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            let res_dir = app.path().resource_dir().expect("resource dir");
            let backend_path = res_dir.join("backend").join("server.py");

            // Only start backend if port 8767 is not already running
            let already_running = TcpStream::connect_timeout(
                &"127.0.0.1:8767".parse().unwrap(),
                Duration::from_millis(500),
            ).is_ok();

            if !already_running {
                let child = if backend_path.exists() {
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
                if let Some(ref c) = child {
                    println!("✅ Backend started (pid={})", c.id());
                }
                *app.state::<BackendProcess>().0.lock().unwrap() = child;
            } else {
                println!("✅ Backend already running on :8767");
            }

            // Wait for backend
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

            // Remove any existing window with label "main" before creating new one
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.close();
            }

            tauri::WebviewWindowBuilder::new(
                app,
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
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.try_state::<BackendProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(ref mut child) = *guard {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error running X-Video");
}

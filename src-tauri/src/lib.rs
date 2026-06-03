use tauri::Manager;
use std::process::{Child, Command};
use std::sync::Mutex;

struct BackendProcess(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            // Get resource directory where backend is bundled
            let res_dir = app.path().resource_dir().expect("resource dir");
            let backend_path = res_dir.join("backend").join("server.py");

            // Start Python backend server
            let child = if backend_path.exists() {
                Command::new("python3")
                    .args(["-u", backend_path.to_str().unwrap()])
                    .current_dir(res_dir)
                    .spawn()
                    .ok()
            } else {
                // Fallback: try development path
                Command::new("python3")
                    .args(["-u", "backend/server.py"])
                    .spawn()
                    .ok()
            };

            if let Some(ref c) = child {
                println!("X-Video backend started (pid: {})", c.id());
            }
            *app.state::<BackendProcess>().0.lock().unwrap() = child;

            // Wait for backend to be ready (poll /healthz)
            std::thread::spawn(|| {
                let url = "http://localhost:8767/healthz";
                for _ in 0..30 {
                    std::thread::sleep(std::time::Duration::from_secs(1));
                    if let Ok(resp) = reqwest::blocking::get(url) {
                        if resp.status().is_success() {
                            break;
                        }
                    }
                }
            });

            // Give backend a moment, then load it
            std::thread::sleep(std::time::Duration::from_secs(3));

            let _window = tauri::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::External("http://localhost:8767".parse().unwrap()),
            )
            .title("X-Video Studio — AI World")
            .inner_size(1440.0, 900.0)
            .min_inner_size(1024.0, 700.0)
            .resizable(true)
            .fullscreen(false)
            .center()
            .build()
            .expect("failed to build window");

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                // Kill backend process on app close
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

use std::process::Command;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|_app| {
            // Open browser to the X-Video server
            std::thread::spawn(|| {
                std::thread::sleep(std::time::Duration::from_millis(300));
                let url = "http://192.168.1.12:8767";
                let _ = Command::new("open").arg(url).spawn();
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error running X-Video");
}

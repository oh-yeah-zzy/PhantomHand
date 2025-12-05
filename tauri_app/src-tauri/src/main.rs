//! PhantomHand Tauri 主程序
//!
//! 负责启动 Python 后端 sidecar 并管理应用生命周期

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use tauri::{
    api::process::{Command, CommandEvent},
    Manager, SystemTray, SystemTrayEvent, SystemTrayMenu, CustomMenuItem,
};
use std::sync::Mutex;

/// 全局状态：存储后端进程句柄
struct AppState {
    backend_running: Mutex<bool>,
}

/// 启动 Python 后端 sidecar
fn start_backend(app_handle: &tauri::AppHandle) -> Result<(), String> {
    let (mut rx, _child) = Command::new_sidecar("PhantomHandBackend")
        .map_err(|e| format!("无法创建 sidecar: {}", e))?
        .args(["--port", "8765"])
        .spawn()
        .map_err(|e| format!("无法启动后端: {}", e))?;

    // 在后台线程监听后端输出
    let app_handle_clone = app_handle.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    println!("[Backend] {}", line);
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("[Backend Error] {}", line);
                }
                CommandEvent::Error(err) => {
                    eprintln!("[Backend Fatal] {}", err);
                    // 可以通知前端后端崩溃
                    let _ = app_handle_clone.emit_all("backend-error", err);
                }
                CommandEvent::Terminated(payload) => {
                    println!("[Backend] 进程退出: {:?}", payload);
                    let _ = app_handle_clone.emit_all("backend-stopped", ());
                }
                _ => {}
            }
        }
    });

    println!("[Tauri] 后端已启动");
    Ok(())
}

/// 创建系统托盘菜单
fn create_tray_menu() -> SystemTrayMenu {
    let show = CustomMenuItem::new("show".to_string(), "显示窗口");
    let hide = CustomMenuItem::new("hide".to_string(), "隐藏窗口");
    let quit = CustomMenuItem::new("quit".to_string(), "退出");

    SystemTrayMenu::new()
        .add_item(show)
        .add_item(hide)
        .add_native_item(tauri::SystemTrayMenuItem::Separator)
        .add_item(quit)
}

/// Tauri 命令：获取后端状态
#[tauri::command]
fn get_backend_status(state: tauri::State<AppState>) -> bool {
    *state.backend_running.lock().unwrap()
}

/// Tauri 命令：重启后端
#[tauri::command]
async fn restart_backend(app_handle: tauri::AppHandle) -> Result<String, String> {
    // 注意：这里简化处理，实际可能需要先停止旧进程
    start_backend(&app_handle)?;
    Ok("后端已重启".to_string())
}

fn main() {
    let system_tray = SystemTray::new().with_menu(create_tray_menu());

    tauri::Builder::default()
        .manage(AppState {
            backend_running: Mutex::new(false),
        })
        .system_tray(system_tray)
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::LeftClick { .. } => {
                // 左键点击显示窗口
                if let Some(window) = app.get_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            SystemTrayEvent::MenuItemClick { id, .. } => match id.as_str() {
                "show" => {
                    if let Some(window) = app.get_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "hide" => {
                    if let Some(window) = app.get_window("main") {
                        let _ = window.hide();
                    }
                }
                "quit" => {
                    std::process::exit(0);
                }
                _ => {}
            },
            _ => {}
        })
        .setup(|app| {
            // 启动后端
            if let Err(e) = start_backend(&app.handle()) {
                eprintln!("[Tauri] 启动后端失败: {}", e);
                // 可以选择继续运行（仅前端）或退出
            } else {
                let state = app.state::<AppState>();
                *state.backend_running.lock().unwrap() = true;
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_backend_status,
            restart_backend
        ])
        .run(tauri::generate_context!())
        .expect("运行 Tauri 应用时出错");
}

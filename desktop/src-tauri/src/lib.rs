//! The packaged backend, as the window sees it. No Tauri here, so `cargo test` needs no window.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::os::windows::process::CommandExt;
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

pub const ADDRESS: &str = "127.0.0.1:8765";
pub const PAGE: &str = "http://127.0.0.1:8765/";
pub const ENGINE: &str = "court-booker/court-booker.exe";

const CREATE_NO_WINDOW: u32 = 0x0800_0000;
const CONNECT_TIMEOUT: Duration = Duration::from_millis(500);
const ANSWER_TIMEOUT: Duration = Duration::from_secs(2);
const START_POLL: Duration = Duration::from_millis(200);
/// A first start can wait on a virus scan of the folder.
const START_TIMEOUT: Duration = Duration::from_secs(60);

/// The backend started here, if any.
#[derive(Default)]
pub struct Backend(Mutex<Option<Child>>);

impl Backend {
    /// Start `engine serve` without a window; a backend found running stays out of this.
    pub fn start(&self, engine: &Path) -> std::io::Result<()> {
        let child = Command::new(engine)
            .arg("serve")
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(CREATE_NO_WINDOW)
            .spawn()?;
        *self.0.lock().expect("backend lock") = Some(child);
        Ok(())
    }

    /// Stop the backend started here; a backend found running stays.
    pub fn stop(&self) {
        if let Some(mut child) = self.0.lock().expect("backend lock").take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }

    /// Return whether the backend started here has already exited.
    fn exited(&self) -> bool {
        match self.0.lock().expect("backend lock").as_mut() {
            Some(child) => !matches!(child.try_wait(), Ok(None)),
            None => false,
        }
    }

    /// Wait until a backend answers at `address`; one that exits or stays silent is a failure.
    pub fn wait_until_ready(&self, address: &str) -> bool {
        let started = Instant::now();
        while started.elapsed() < START_TIMEOUT {
            if backend_answers(address) {
                return true;
            }
            if self.exited() {
                return false;
            }
            thread::sleep(START_POLL);
        }
        false
    }
}

/// Return whether `answer` is the response of a healthy backend.
fn is_healthy(answer: &str) -> bool {
    answer.starts_with("HTTP/1.1 200") && answer.contains(r#""status":"ok""#)
}

/// Return whether a backend answers at `address`.
pub fn backend_answers(address: &str) -> bool {
    let Ok(address) = address.parse::<SocketAddr>() else {
        return false;
    };
    let Ok(mut stream) = TcpStream::connect_timeout(&address, CONNECT_TIMEOUT) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(ANSWER_TIMEOUT));
    let request = "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n";
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }
    let mut answer = String::new();
    stream.read_to_string(&mut answer).is_ok() && is_healthy(&answer)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    /// Answer one request with `answer` and return the listener's address.
    fn answer_once(answer: &'static str) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
        let address = listener.local_addr().expect("address").to_string();
        thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("accept");
            let mut request = [0; 512];
            let _ = stream.read(&mut request);
            stream.write_all(answer.as_bytes()).expect("write");
        });
        address
    }

    #[test]
    fn a_backend_that_says_ok_answers() {
        let body = "HTTP/1.1 200 OK\r\n\r\n{\"status\":\"ok\",\"version\":\"0.19.0\"}";
        assert!(backend_answers(&answer_once(body)));
    }

    #[test]
    fn another_program_on_the_port_does_not_answer() {
        assert!(!backend_answers(&answer_once("HTTP/1.1 200 OK\r\n\r\n<html>")));
        assert!(!backend_answers(&answer_once("HTTP/1.1 500 Oops\r\n\r\n")));
    }

    #[test]
    fn nothing_on_the_port_does_not_answer() {
        let free = TcpListener::bind("127.0.0.1:0").expect("bind");
        let address = free.local_addr().expect("address").to_string();
        drop(free);
        assert!(!backend_answers(&address));
    }

    #[test]
    fn a_backend_that_exits_is_not_waited_for() {
        let backend = Backend::default();
        let system = std::env::var("SystemRoot").expect("SystemRoot");
        let exits_at_once = Path::new(&system).join("System32").join("where.exe");
        backend.start(&exits_at_once).expect("start");

        let free = TcpListener::bind("127.0.0.1:0").expect("bind");
        let address = free.local_addr().expect("address").to_string();
        drop(free);
        assert!(!backend.wait_until_ready(&address));
    }

    #[test]
    fn stop_without_a_backend_does_nothing() {
        Backend::default().stop();
    }
}

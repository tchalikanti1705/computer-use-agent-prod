import base64, shlex, subprocess, time, structlog
from shared.observability import ACTION_LATENCY
logger = structlog.get_logger()
DISPLAY = ":99"

def docker_exec(cmd: str, container_name: str, decode=True):
    safe_cmd = cmd.replace('"', '\\"')
    full = f'docker exec {container_name} sh -lc "{safe_cmd}"'
    out = subprocess.check_output(full, shell=True, timeout=30)
    return out.decode("utf-8", errors="ignore") if decode else out

def docker_exec_display(cmd: str, container_name: str, decode=True):
    return docker_exec(f"export DISPLAY={DISPLAY} && {cmd}", container_name, decode)

class VMController:
    def __init__(self, container_name: str):
        self.cn = container_name

    def capture_screenshot(self) -> bytes:
        docker_exec_display("import -window root /tmp/screen.png", self.cn)
        return docker_exec("cat /tmp/screen.png", self.cn, decode=False)

    def capture_screenshot_base64(self) -> str:
        return base64.b64encode(self.capture_screenshot()).decode()

    def mouse_move(self, x, y):
        docker_exec_display(f"xdotool mousemove {x} {y}", self.cn)

    def click(self, x, y, button=1):
        t = time.time()
        docker_exec_display(f"xdotool mousemove {x} {y} click {button}", self.cn)
        ACTION_LATENCY.labels(action_type="click").observe(time.time() - t)

    def double_click(self, x, y, button=1):
        docker_exec_display(f"xdotool mousemove {x} {y} click --repeat 2 {button}", self.cn)

    def type_text(self, text):
        t = time.time()
        docker_exec_display(f"xdotool type --delay 50 {shlex.quote(text)}", self.cn)
        ACTION_LATENCY.labels(action_type="type").observe(time.time() - t)

    def keypress(self, key):
        docker_exec_display(f"xdotool key {shlex.quote(key)}", self.cn)

    def scroll(self, direction="down", amount=3):
        btn = 5 if direction == "down" else 4
        for _ in range(amount):
            docker_exec_display(f"xdotool click {btn}", self.cn)

    def ensure_firefox(self, wait=3):
        try:
            if docker_exec("pgrep -a firefox", self.cn).strip(): return
        except: pass
        docker_exec_display("nohup firefox >/tmp/firefox.log 2>&1 &", self.cn)
        time.sleep(wait)

    def is_alive(self) -> bool:
        try: docker_exec("echo ok", self.cn); return True
        except: return False

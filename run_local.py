#!/usr/bin/env python3
"""
CLI mode — run like the original:

    python run_local.py --message "search for hirings near me"

Then open VNC viewer at localhost:5900 and watch the agent work.

This bypasses the full API/queue/scheduler stack and runs the agent loop
directly against a single Docker container — perfect for local dev and demos.
"""
import argparse
import base64
import os
import sys
import time
import subprocess

from dotenv import load_dotenv

load_dotenv()

# ── Ensure the sandbox container is running ──

CONTAINER_NAME = "cua-local"
SANDBOX_IMAGE = "cua-sandbox:latest"
VNC_PORT = 5900


def ensure_sandbox():
    """Start the sandbox container if not already running."""
    try:
        out = subprocess.check_output(
            f"docker inspect -f '{{{{.State.Running}}}}' {CONTAINER_NAME}",
            shell=True, stderr=subprocess.DEVNULL
        ).decode().strip()
        if out == "true":
            print(f"✓ Sandbox already running: {CONTAINER_NAME}")
            print(f"  VNC: localhost:{VNC_PORT}")
            return
    except subprocess.CalledProcessError:
        pass

    # Remove stale container if exists
    subprocess.run(f"docker rm -f {CONTAINER_NAME}", shell=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"Starting sandbox container: {CONTAINER_NAME}")
    subprocess.check_call([
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", f"{VNC_PORT}:5900",
        SANDBOX_IMAGE,
    ])
    print(f"✓ Sandbox started!")
    print(f"  VNC: localhost:{VNC_PORT} (password: secret)")
    print(f"  Waiting for desktop to load...")
    time.sleep(5)


# ── Import agent components ──

from agent_runtime.vm.controller import VMController
from agent_runtime.safety.engine import SafetyEngine
from agent_runtime.llm.router import LLMRouter
from shared.config import get_settings


def run_local(message: str):
    """Run the agent loop locally — same as original main.py but with safety + LLM router."""

    ensure_sandbox()
    settings = get_settings()

    # Setup components
    vm = VMController(CONTAINER_NAME)
    vm.ensure_firefox(wait=4)

    # Default tenant config for local mode
    tenant_config = {
        "allowed_domains": [
            "google.com", "www.google.com",
            "wikipedia.org", "www.wikipedia.org",
            "weather.com", "www.weather.com",
            "indeed.com", "www.indeed.com",
            "linkedin.com", "www.linkedin.com",
        ],
        "require_human_approval": False,
        "llm_provider": settings.default_llm_provider,
        "llm_model": settings.default_llm_model,
    }

    safety = SafetyEngine("local", tenant_config)
    llm = LLMRouter(tenant_config)

    print(f"\n{'='*60}")
    print(f"  TASK: {message}")
    print(f"  Open VNC viewer at localhost:{VNC_PORT} to watch!")
    print(f"{'='*60}\n")

    # Step 0: Initial screenshot + first LLM call
    step = 0
    total_tokens = 0

    screenshot_b64 = vm.capture_screenshot_base64()
    vm_screenshot_to_file(vm, step)

    print(f"[Step {step}] Sending initial screenshot to LLM...")
    response = llm.initial_response(message, screenshot_b64)
    response_id = response["id"]
    total_tokens += response["usage"]["total_tokens"]

    for msg in response.get("messages", []):
        print(f"  MODEL: {msg}")

    # Main loop
    max_steps = settings.max_agent_steps

    while step < max_steps:
        computer_call = response.get("computer_call")

        if computer_call is None:
            print(f"\n✓ TASK COMPLETE after {step} steps ({total_tokens} tokens)")
            for msg in response.get("messages", []):
                print(f"  RESULT: {msg}")
            return

        actions = computer_call.get("actions", [])
        call_id = computer_call.get("call_id", "")

        # Safety check
        verdict = safety.validate_batch(actions)
        if not verdict.allowed:
            print(f"\n✗ SAFETY BLOCKED at step {step}: {verdict.reason}")
            return

        # Execute actions
        for action in actions:
            atype = action.get("type", "")
            print(f"[Step {step}] ACTION: {action_to_str(action)}")

            if atype == "click":
                btn = {"left": 1, "middle": 2, "right": 3}.get(action.get("button", "left"), 1)
                vm.click(action["x"], action["y"], btn)
            elif atype == "double_click":
                btn = {"left": 1, "middle": 2, "right": 3}.get(action.get("button", "left"), 1)
                vm.double_click(action["x"], action["y"], btn)
            elif atype == "move":
                vm.mouse_move(action["x"], action["y"])
            elif atype == "scroll":
                vm.mouse_move(action.get("x", 0), action.get("y", 0))
                sy = action.get("scrollY", 0)
                if sy > 0:
                    vm.scroll("down", max(1, abs(sy) // 200))
                elif sy < 0:
                    vm.scroll("up", max(1, abs(sy) // 200))
            elif atype == "keypress":
                keys = action.get("keys", [])
                KEY_MAP = {
                    "ENTER": "Return", "RETURN": "Return", "SPACE": "space",
                    "TAB": "Tab", "ESC": "Escape", "BACKSPACE": "BackSpace",
                    "DELETE": "Delete", "UP": "Up", "DOWN": "Down",
                    "LEFT": "Left", "RIGHT": "Right", "CTRL": "ctrl",
                    "ALT": "alt", "SHIFT": "shift",
                }
                mapped = [KEY_MAP.get(str(k).upper(), str(k)) for k in keys]
                vm.keypress("+".join(mapped) if len(mapped) > 1 else mapped[0])
            elif atype == "type":
                vm.type_text(action.get("text", ""))
            elif atype == "wait":
                time.sleep(2)

        step += 1
        time.sleep(settings.step_delay_seconds)

        # Capture new screenshot
        screenshot_b64 = vm.capture_screenshot_base64()
        vm_screenshot_to_file(vm, step)

        # Next LLM call
        print(f"[Step {step}] Sending screenshot to LLM...")
        response = llm.continuation(response_id, call_id, screenshot_b64)
        response_id = response["id"]
        total_tokens += response["usage"]["total_tokens"]

        for msg in response.get("messages", []):
            print(f"  MODEL: {msg}")

    print(f"\n✗ Max steps ({max_steps}) exceeded")


def vm_screenshot_to_file(vm: VMController, step: int):
    """Save screenshot locally for debugging."""
    try:
        png = vm.capture_screenshot()
        with open("latest_screen.png", "wb") as f:
            f.write(png)
    except Exception:
        pass


def action_to_str(action: dict) -> str:
    """Pretty-print an action."""
    t = action.get("type", "?")
    if t in ("click", "double_click", "move"):
        return f"{t}(x={action.get('x')}, y={action.get('y')})"
    if t == "type":
        return f"type({action.get('text', '')!r})"
    if t == "keypress":
        return f"keypress({action.get('keys', [])})"
    if t == "scroll":
        return f"scroll(scrollY={action.get('scrollY', 0)})"
    return str(action)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the computer-use agent locally (watch via VNC)"
    )
    parser.add_argument(
        "--message", "-m",
        required=True,
        help="Task instruction for the agent"
    )
    args = parser.parse_args()
    run_local(args.message)

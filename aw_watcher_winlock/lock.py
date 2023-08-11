import ctypes
import logging
import platform
import os
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import Optional

from aw_core.models import Event
from aw_client import ActivityWatchClient

from .config import load_config

system = platform.system()

if system != "Windows":
    raise Exception(f"Unsupported platform: {system}")


logger = logging.getLogger(__name__)
td1ms = timedelta(milliseconds=1)


class Settings:
    def __init__(self, config_section, timeout=None, poll_time=None):
        # Time without input before we're considering the user as AFK
        self.timeout = timeout or config_section["timeout"]
        # How often we should poll for input activity
        self.poll_time = poll_time or config_section["poll_time"]

        assert self.timeout >= self.poll_time


def screen_locked():
    """
    Find if the user has locked their screen.
    """
    user32 = ctypes.windll.User32
    kernel32 = ctypes.windll.Kernel32
    psapi = ctypes.windll.Psapi
    GetForegroundWindow = user32.GetForegroundWindow
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId
    OpenProcess = kernel32.OpenProcess
    GetModuleFileNameEx = psapi.GetModuleFileNameExW
    GetWindowText = user32.GetWindowTextW
    PROCESS_ALL_ACCESS = 0x1F0FFF

    try:
        hwnd = GetForegroundWindow()
        pid = ctypes.c_ulong(0)
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        buf = ctypes.create_unicode_buffer(1024)
        GetModuleFileNameEx(handle, None, buf, 1024)
        exe = os.path.basename(buf.value)
        title = ctypes.create_unicode_buffer(1024)
        GetWindowText(hwnd, title, 1024)
        title = title.value

        return "Logon" in title or "Logon" in exe or "LockApp" in exe or "Lock Screen" in title
    except Exception as e:
        logger.error(f"Error while checking if screen is locked: {e}")
        return False

class LockWatcher:
    def __init__(self, args, testing=False):
        # Read settings from config
        self.settings = Settings(
            load_config(testing), timeout=args.timeout, poll_time=args.poll_time
        )

        self.client = ActivityWatchClient(
            "aw-watcher-winlock", host=args.host, port=args.port, testing=testing
        )
        self.bucketname = "{}_{}".format(
            self.client.client_name, self.client.client_hostname
        )

    def ping(self, afk: bool, timestamp: datetime, duration: float = 0):
        data = {"status": "afk" if afk else "not-afk"}
        e = Event(timestamp=timestamp, duration=duration, data=data)
        pulsetime = self.settings.timeout + self.settings.poll_time
        self.client.heartbeat(self.bucketname, e, pulsetime=pulsetime, queued=True)

    def run(self):
        logger.info("aw-watcher-winlock started")

        # Initialization
        sleep(1)

        eventtype = "afkstatus"
        self.client.create_bucket(self.bucketname, eventtype, queued=True)

        # Start afk checking loop
        with self.client:
            self.heartbeat_loop()

    def heartbeat_loop(self):
        afk = False
        last_unlocked = datetime.now(timezone.utc)
        last_locked = datetime.now(timezone.utc)
        while True:
            try:
                now = datetime.now(timezone.utc)

                locked = screen_locked()
                if locked:
                    last_locked = now
                else:
                    last_unlocked = now
                
                seconds_since_input = (now - last_unlocked).total_seconds()

                logger.debug(f"at {now}: locked={locked}")

                # If no longer AFK
                if afk and seconds_since_input < self.settings.timeout:
                    logger.info("No longer AFK")
                    self.ping(afk, timestamp=last_unlocked)
                    afk = False
                    # ping with timestamp+1ms with the next event (to ensure the latest event gets retrieved by get_event)
                    self.ping(afk, timestamp=last_unlocked + td1ms)
                # If becomes AFK
                elif not afk and seconds_since_input >= self.settings.timeout:
                    logger.info("Became AFK")
                    self.ping(afk, timestamp=last_unlocked)
                    afk = True
                    # ping with timestamp+1ms with the next event (to ensure the latest event gets retrieved by get_event)
                    self.ping(
                        afk, timestamp=last_unlocked + td1ms, duration=seconds_since_input
                    )
                # Send a heartbeat if no state change was made
                else:
                    if afk:
                        self.ping(
                            afk, timestamp=last_unlocked, duration=seconds_since_input
                        )
                    else:
                        self.ping(afk, timestamp=last_unlocked)

                sleep(self.settings.poll_time)

            except KeyboardInterrupt:
                logger.info("aw-watcher-winlock stopped by keyboard interrupt")
                break
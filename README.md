# ActivityWatch watcher for Windows Locked as AFK status

This is a simple watcher for [ActivityWatch](https://activitywatch.net/) that sets the user's status to AFK when the computer is locked and back to active when it is unlocked.

## Build

Tested on Python 3.10.4 on Windows.

```bash
pyinstaller cli.py -n aw-watcher-winlock --onefile
```

Copy `dist/aw-watcher-winlock.exe` to somewhere in your PATH, and your aw-qt should recognize it.

## Credits

Many code from the official [aw-watcher-afk](https://github.com/ActivityWatch/aw-watcher-afk) repo.

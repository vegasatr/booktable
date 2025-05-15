from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import subprocess
import os

class ChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            print(f'{event.src_path} изменен, перезапуск бота...')
            subprocess.run(['pkill', '-f', 'gpt-bot.py'])
            subprocess.run(['python3', 'gpt-bot.py'])

if __name__ == "__main__":
    path = '.'
    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

import time
import subprocess
import signal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Global variable to store the running SAM process
sam_process = None

EXCLUDED_DIRS = [".aws-sam"]  # Ignore .aws-sam directory

class FileChangeHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        if any(excluded in event.src_path for excluded in EXCLUDED_DIRS):
            return  # Ignore changes in .aws-sam
        
        if event.src_path.endswith((".py")) and event.event_type in ["modified", "created"]:
            print(f"🔄 File changed: {event.src_path}. Rebuilding and restarting...")
            restart_sam()

def restart_sam():
    global sam_process
    if sam_process:
        sam_process.terminate()  # Stop previous instance
        sam_process.wait()  # Ensure it's fully stopped
    print("👀 Watching for file changes (excluding .aws-sam)...")
    print("⚙️ Rebuilding SAM...")
    subprocess.run(["sam", "build"])

    # print("🚀 Starting SAM local API...")
    # sam_process = subprocess.Popen(["sam", "local", "start-api"])

def watch():
    global sam_process
    print("🏗️ Initial build and start...")
    restart_sam()  # Start the API initially

    path = "."  # Watch current directory
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping watcher...")
        observer.stop()
        if sam_process:
            sam_process.terminate()
            sam_process.wait()
    observer.join()

if __name__ == "__main__":
    watch()
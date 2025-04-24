import os
import sys

# Add the following code at the BEGINNING of your application
# to enable remote debugging
try:
    import pydevd_pycharm
    pydevd_is_available = True
except ImportError:
    pydevd_is_available = False

if pydevd_is_available:
    try:
        # The host should be the machine running IntelliJ/PyCharm
        host = os.environ.get("DEBUG_HOST", "host.docker.internal")
        port = int(os.environ.get("DEBUG_PORT", 5678))
        
        print(f"Trying to connect to debugger at {host}:{port}")
        pydevd_pycharm.settrace(host, port=port, stdoutToServer=True, stderrToServer=True, suspend=False)
        print("Connected to remote debugger")
    except Exception as e:
        print(f"Error connecting to debugger: {e}")
        print("Continuing without debugger")

# Import and run the actual application
import uvicorn
from main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting application on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)
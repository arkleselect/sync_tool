import os
import sys
from flask import Flask, render_template, request, send_from_directory, jsonify, url_for
from flask_socketio import SocketIO, emit
import engineio.async_drivers.threading

# --- 1. 资源路径处理 ---
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# --- 2. 初始化 App ---
app = Flask(__name__, 
            template_folder=resource_path('templates'),
            static_folder=resource_path('static'))

app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 * 1024 

# =========== 关键修改在这里 ===========
# 显式指定 async_mode='threading'，防止打包后报错
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
# ====================================

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

current_text = ""

def print_banner():
    """打印启动 Banner"""
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

    # 获取本机 IP 提示用户
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1"

    banner = f"""
{CYAN}{BOLD}
  _______  _______  _______  __         
 |       ||       ||       ||  |        
 |_     _||   _   ||   _   ||  |        
   |   |  |  | |  ||  | |  ||  |        
   |   |  |  |_|  ||  |_|  ||  |__      
   |___|  |_______||_______||____|      
{RESET}
{YELLOW}>>> TOOL ACTION: SERVICE STARTING...{RESET}
{GREEN}[+] Mode: Sync & Transfer (Max: 50GB){RESET}
{GREEN}[+] Upload Folder: {UPLOAD_FOLDER}{RESET}
{GREEN}[+] Local Access:  http://127.0.0.1:5001{RESET}
{CYAN}[+] Network Access: http://{local_ip}:5001 (Share this IP){RESET}
    """
    print(banner)

# --- 路由定义 ---
@app.route("/")
def index():
    try:
        all_files = os.listdir(UPLOAD_FOLDER)
        visible_files = [f for f in all_files if not f.startswith('.')]
        files = sorted(
            visible_files,
            key=lambda x: os.path.getmtime(os.path.join(UPLOAD_FOLDER, x)),
            reverse=True
        )
    except Exception:
        files = []
    return render_template("index.html", initial_text=current_text, initial_files=files)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@socketio.on("send_text")
def handle_send_text(data):
    global current_text
    current_text = data["text"]
    emit("update_text", {"text": current_text}, broadcast=True)

@app.route("/upload", methods=["POST"])
def upload_file():
    if "files" not in request.files:
        return jsonify({"success": False, "message": "No file part"})
    
    files = request.files.getlist("files")
    uploaded_files = []

    for file in files:
        if file.filename == "":
            continue
        
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        try:
            file.save(filepath)
            uploaded_files.append(file.filename)
            socketio.emit("new_file", {"filename": file.filename})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

    return jsonify({"success": True, "filenames": uploaded_files})

@app.route("/delete/<filename>", methods=["DELETE"])
def delete_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            socketio.emit("file_deleted", {"filename": filename})
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})
    return jsonify({"success": False, "message": "文件不存在"})

@app.route("/uploads/<filename>")
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"success": False, "message": "文件过大，超过 50GB 限制"}), 413

if __name__ == "__main__":
    print_banner()
    # allow_unsafe_werkzeug=True 允许在生产/打包环境使用 socketio
    socketio.run(app, host="0.0.0.0", port=5001, allow_unsafe_werkzeug=True)

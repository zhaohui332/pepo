"""兆辉防腐科技 · 文章运营助手 - 启动入口

双击/运行此文件即启动服务并自动打开浏览器。
支持本地运行和 PyInstaller 打包。
"""
import os
import sys
import webbrowser
import threading
import time

# 确保在正确的目录下
if getattr(sys, 'frozen', False):
    # PyInstaller 打包模式 - 临时目录
    os.chdir(sys._MEIPASS)
else:
    # 普通 Python 运行模式
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

import uvicorn

def open_browser(port):
    """延迟 1.5 秒后自动打开浏览器"""
    time.sleep(1.5)
    url = f"http://localhost:{port}"
    print(f"🌐 正在打开浏览器: {url}")
    webbrowser.open(url)

def print_banner(port):
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║   江苏兆辉防腐科技 · 文章运营助手        ║")
    print("  ║   智能多平台文章生成工具                  ║")
    print("  ╠══════════════════════════════════════════╣")
    print(f"  ║   🌐 http://localhost:{port}                 ║")
    print("  ║   📋 按 Ctrl+C 停止服务                  ║")
    print("  ╚══════════════════════════════════════════╝")
    print()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8350))
    host = os.getenv("HOST", "127.0.0.1")

    print_banner(port)

    # 自动打开浏览器
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # 导入并启动 app
    from app import app
    uvicorn.run(app, host=host, port=port, log_level="info")

from flask import Flask, send_from_directory
import os

app = Flask(__name__)
PORT = int(os.environ.get("PORT", 8080))

@app.route('/')
def home():
    return '<h1>🪞 ЗЕРКАЛО</h1><p><a href="/webapp">Открыть</a></p>'

@app.route('/webapp')
def webapp():
    return send_from_directory('webapp', 'index.html')

@app.route('/webapp/<path:filename>')
def webapp_files(filename):
    return send_from_directory('webapp', filename)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT)

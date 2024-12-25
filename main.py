from flask import Flask, request, render_template, send_file, jsonify
from werkzeug.utils import secure_filename
from pydub import AudioSegment
from pydub.effects import normalize
import os
import hashlib

app = Flask(__name__)

# Настройки для загрузки файлов
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'mp3', 'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# Проверка допустимого расширения файла
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Генерация уникального идентификатора на основе браузерных характеристик
def generate_unique_id(user_agent):
    return hashlib.md5(user_agent.encode()).hexdigest()

# Главная страница
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Обработка загрузки файла
@app.route('/upload', methods=['POST'])
def upload():
    user_agent = request.headers.get('User-Agent')
    unique_id = generate_unique_id(user_agent)

    if 'file' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        filename = f"{unique_id}_{original_filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return jsonify({'file_path': file_path, 'unique_id': unique_id, 'original_filename': original_filename}), 200
    return jsonify({'error': 'Недопустимый формат файла'}), 400

# Обработка настроек и возврат файла
@app.route('/process', methods=['POST'])
def process():
    data = request.json
    file_path = data.get('file_path')
    unique_id = data.get('unique_id')
    original_filename = data.get('original_filename')
    volume_change = float(data.get('volume', 0))
    speed_change = float(data.get('speed', 1))
    pitch_change = float(data.get('pitch', 0))
    start_trim = int(data.get('start_trim', 0))  # Начало обрезки в миллисекундах
    end_trim = int(data.get('end_trim', 0))  # Конец обрезки в миллисекундах
    add_silence_start = int(data.get('add_silence_start', 0))  # Добавить тишину в начале
    add_silence_end = int(data.get('add_silence_end', 0))  # Добавить тишину в конце
    echo_effect = data.get('echo_effect', False)  # Добавить эффект эха
    normalize_audio = data.get('normalize_audio', False)  # Нормализация аудио

    # Загрузка аудиофайла
    audio = AudioSegment.from_file(file_path)

    # Обрезка аудио
    if start_trim > 0 or end_trim > 0:
        audio = audio[start_trim:len(audio) - end_trim]

    # Добавление тишины в начале и конце
    if add_silence_start > 0:
        audio = AudioSegment.silent(duration=add_silence_start) + audio
    if add_silence_end > 0:
        audio = audio + AudioSegment.silent(duration=add_silence_end)

    # Изменение громкости
    if volume_change != 0:
        audio = audio + volume_change

    # Нормализация аудио
    if normalize_audio:
        audio = normalize(audio)

    # Добавление эффекта эха
    if echo_effect:
        audio = audio.overlay(audio, loop=True, gain_during_overlay=-10)

    # Изменение скорости и тональности
    if speed_change != 1 or pitch_change != 0:
        audio = audio._spawn(audio.raw_data, overrides={
            "frame_rate": int(audio.frame_rate * speed_change)
        }).set_frame_rate(audio.frame_rate)

    # Сохранение обработанного файла
    processed_filename = f"{unique_id}_processed.mp3"
    processed_file_path = os.path.join(app.config['PROCESSED_FOLDER'], processed_filename)
    audio.export(processed_file_path, format="mp3")

    return jsonify({'processed_file_path': processed_file_path, 'original_filename': original_filename}), 200

# Скачивание файла
@app.route('/download/<path:file_path>')
def download(file_path):
    original_filename = request.args.get('original_filename')
    return send_file(file_path, as_attachment=True, download_name=original_filename)

if __name__ == '__main__':
    # Создание папок для загрузки файлов, если они не существуют
    for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER]:
        if not os.path.exists(folder):
            os.makedirs(folder)
    app.run(debug=True)
from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify, flash,send_from_directory
import datetime
import cv2
import sqlitecloud
import requests
import os
import time
from functools import wraps
import logging
import numpy as np
import threading
import signal
import subprocess
import sys
import psutil
from app import run_app

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = 'a643ab7db1402aa452bdc9ec40a9a62e'

# Set CUDA_LAUNCH_BLOCKING=1 for more accurate CUDA error reporting
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'

def stop_and_run_app():
    print("Stopping existing app.py and starting a new instance...")

    # Find and terminate existing app.py process
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        # Check if the process is app.py
        if 'app.py' in proc.info['cmdline']:
            print(f"Killing existing app.py with PID: {proc.info['pid']}")
            proc.terminate()  # Send a termination signal

            # Wait for the process to terminate
            proc.wait()  # Wait for the process to terminate
            print(f"app.py with PID {proc.info['pid']} has been terminated.")

            # Optional: Wait a moment to ensure the process has completely exited
            time.sleep(1)  # Adjust this sleep duration as needed

    # After terminating all existing processes, start a new instance
    print("Starting a new instance of app.py...")
    run_app()  # Run the Flask app in the main thread



# Connect to SQLite database
def get_db_connection():
    conn = sqlitecloud.connect('sqlitecloud://cbff1ztjiz.sqlite.cloud:8860/cctvdb.sqlite?apikey=H9MXnqPGK8bwDT3iOczW3j9VObuLTa6dqIau1d027Tg')
    conn.execute(f"USE DATABASE cctvdb.sqlite")
    conn.row_factory = sqlitecloud.Row
    return conn

# def save_detection_video(frame, room_name, device_number, label):
#     timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
#     date = datetime.datetime.now().strftime("%Y-%m-%d")
    
#     # Create directory with the current date if it doesn't exist
#     directory_path = f'static/videos/{date}'
#     if not os.path.exists(directory_path):
#         os.makedirs(directory_path)
    
#     video_path = f'{directory_path}/{room_name}{device_number}{label}_{timestamp}.mp4'
#     fourcc = cv2.VideoWriter_fourcc(*'XVID')
#     out = cv2.VideoWriter(video_path, fourcc, 20.0, (640,480))
#     out.write(frame)
#     out.release()
    
#     return video_path


# def send_database_to_other_app():
#     conn = get_db_connection()
#     cursor = conn.cursor()

#     # Fetch all data from the database
#     cursor.execute("SELECT * FROM devices")
#     devices = cursor.fetchall()
#     cursor.execute("SELECT * FROM Events")
#     events = cursor.fetchall()
#     cursor.execute("SELECT * FROM alerts")
#     alerts = cursor.fetchall()
#     cursor.execute("SELECT * FROM staff")
#     staff = cursor.fetchall()

#     conn.close()

#     # Convert the fetched data to a list of dictionaries
#     devices_data = [dict(row) for row in devices]
#     events_data = [dict(row) for row in events]
#     alerts_data = [dict(row) for row in alerts]
#     staff_data = [dict(row) for row in staff]

#     # Prepare the payload
#     payload = {
#         "devices": devices_data,
#         "events": events_data,
#         "alerts": alerts_data,
#         "staff": staff_data
#     }
    
#     # Send the data to the other Flask app
#     response = requests.post('http://172.30.143.113:5000/', json=payload, headers={'Content-Type':'application/json'})
#     print(payload)
#     if response.status_code == 200:
#         logging.info("Database data sent successfully.")
#     else:
#         logging.error("Failed to send database data.")


@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    email = request.form['email']
    password = request.form['password']

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
    conn.close()

    if user:
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['username'] = user['username']
        session['hospital'] = user['hospital']
        session['role'] = user['role']
        return redirect(url_for('home'))
    else:
        return "Invalid credentials, please try again."

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/home')
@login_required
def home():
    
    conn = get_db_connection()
    # Fetch user details
    email = session['email']
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    hospital = user['hospital']
    # Fetch devices associated with the user
    devices = conn.execute('SELECT * FROM devices WHERE hospital = ?', (hospital,)).fetchall()
    # Fetch logs associated with the user
    logs = conn.execute('SELECT * FROM Events WHERE hospital = ?', (hospital,)).fetchall()
    # Fetch alerts associated with the user
    alerts = conn.execute('SELECT * FROM alerts WHERE hospital = ?', (hospital,)).fetchall()
    staff = conn.execute('SELECT * FROM staff WHERE hospital = ?', (hospital,)).fetchall()
    conn.close()

    user_details = {
        'email': user['email'],
        'username': user['username'],
        'role': user['role'],
        'hospital': user['hospital']
    }

    # Format devices data
    devices_data = [
        {
            "id": device["id"],
            "DeviceName": device["DeviceName"],
            "RoomNumber": device["RoomNumber"],
            "IPAddress": device["IPAddress"],
            "ModelSelection": device["ModelSelection"],
            "email": device["email"],
            "username": device["username"],
            "hospital": device["hospital"],
            "role": device["role"]
        }
        for device in devices
    ]

    # Format events data
    events_data = [
        {
            "EventID": event["EventID"],
            "EventType": event["EventType"],
            "alerted": event["alerted"],
            "Timestamp": event["Timestamp"],
            "Date": event["Date"],
            "VideoURL": event["VideoURL"],
            "Images": event["Images"],
            "email": event["email"],
            "username": event["username"],
            "hospital": event["hospital"],
            "role": event["role"]
        }
        for event in logs
    ]

    # Format alerts data
    alerts_data = [
        {
            "id": alert["id"],
            "Name": alert["Name"],
            "phone_number": alert["phone_number"],
            "department": alert["department"],
            "hospital": alert["hospital"],
            "email": alert["email"],
            "role": alert["role"]
        }
        for alert in alerts
    ]

    # Format staff data
    staff_data = [
        {
            "id": staff_member["id"],
            "name": staff_member["name"],
            "staff_id": staff_member["staff_id"],
            "department": staff_member["department"],
            "hospital": staff_member["hospital"],
            "mail": staff_member["mail"],
            "mobile": staff_member["mobile"],
            "photo": staff_member["photo"]
        }
        for staff_member in staff
    ]

    # Prepare the payload
    payload = {
        "devices": devices_data,
        "events": events_data,
        "alerts": alerts_data,
        "staff": staff_data
    }
    
    
    # Send the data to the other Flask app
   # response = requests.post('http://127.0.0.1:5000', json=payload, headers={'Content-Type':'application/json'})
    # print(payload)
    # if response.status_code == 200:
    #     logging.info("Database data sent successfully.")
    # else:
    #     logging.error("Failed to send database data.")
    print([device["DeviceName"] for device in devices])
    #logs_data = [dict(log) for log in logs] 
    logs_data = [
    {
        "EventID": event["EventID"],
        "EventType": event["EventType"],
        "alerted": event["alerted"],
        "Timestamp": event["Timestamp"],
        "Date": event["Date"],
        "VideoURL": event["VideoURL"],
        "Images": event["Images"],
        "email": event["email"],
        "username": event["username"],
        "hospital": event["hospital"],
        "role": event["role"]
    }
    for event in logs  # logs is assumed to be a list of Row objects
]
    return render_template('home.html', user=user_details, devices=devices, logs=logs, logsd=logs_data, alerts=alerts, staff=staff, num_cameras=[device["id"] for device in devices])


@app.route('/api/logs')
@login_required  # Ensuring that the user is logged in before accessing the logs
def api_logs():
    conn = get_db_connection()

    # Fetch user details
    email = session['email']
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    hospital = user['hospital']
    
    # Fetch logs associated with the user
    logs = conn.execute('SELECT * FROM Events WHERE hospital = ?', (hospital,)).fetchall()
    conn.close()


    return jsonify(logs)  # Return the formatted logs data as JSON



@app.route('/device_add', methods=['GET', 'POST'])
@login_required
def device_add():
    conn = get_db_connection()
    if request.method == 'POST':
        # camera_name = request.form['CameraName']
        room_name = request.form['roomNumber']
        device_number = request.form['deviceNumber']
        ip_address = request.form['ipAddress']
        # camera_details = request.form['cameraDetails']
        alert_settings = ', '.join(request.form.getlist('alertSetting'))
        email = session['email']
        username = session['username']
        hospital = session['hospital']
        role = session['role']

        # Use a cursor to execute SQL commands
        cursor = conn.cursor()

        # Insert data into the devices table
        cursor.execute('''
            INSERT INTO devices ( DeviceName, RoomNumber, IPAddress, ModelSelection, email, username, hospital, role)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (device_number, room_name, ip_address, alert_settings, email, username, hospital, role))

        # Commit the transaction
        conn.commit()

        # Close the cursor and database connection
        cursor.close()
        conn.close()
        stop_and_run_app()

        return redirect(url_for('home'))

    return render_template('device_add.html')

@app.route('/alerts_add', methods=['GET', 'POST'])
@login_required
def alerts_add():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        dept = request.form['dept']
        email = session['email']
        hos = request.form['hos']
        role = session['role']

        # Use a cursor to execute SQL commands
        cursor = conn.cursor()

        # Insert data into the devices table
        cursor.execute('''
            INSERT INTO alerts (Name, phone_number, department, hospital, email, role)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, mobile, dept, hos, email, role))

        # Commit the transaction
        conn.commit()

        # Close the cursor and database connection
        cursor.close()
        conn.close()

        return redirect(url_for('home'))

    return render_template('alerts_add.html')

@app.route('/staff_add', methods=['GET', 'POST'])
@login_required
def staff_add():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        sid = request.form['sid']
        dept = request.form['dept']
        hos = request.form['hos']
        mail = request.form['mail']
        mobile = request.form['mobile']
        photo = request.files['phto']

        # Save photo to static/uploads directory
        photo_path = f'static/staff/{photo.filename}'
        photo.save(photo_path)
        # Use a cursor to execute SQL commands
        cursor = conn.cursor()

        # Insert data into the devices table
        cursor.execute('''
            INSERT INTO staff (name, staff_id, department, hospital, mail, mobile, photo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, sid, dept, hos, mail, mobile, photo_path))

        # Commit the transaction
        conn.commit()

        # Close the cursor and database connection
        cursor.close()
        conn.close()

        return redirect(url_for('home'))

    return render_template('staff_add.html')




@app.route('/store_data', methods=['POST'])
@login_required
def store_data():
    conn = get_db_connection()
    data = request.json  # Assuming JSON data is sent

    # Extract data from JSON payload
    message = data.get('message')
    phone_number = data.get('phone_number')
    time = data.get('time')
    date = data.get('date')
    email = 'rk@gmail.com'
    username = 'rk'
    hospital = 'SIDS'
    role = 'admin'

    cursor = conn.cursor()

    # Insert data into the devices table
    cursor.execute('''
            INSERT INTO Events (EventType, alerted, Timestamp, Date, VideoURL, Images, email, username, hospital, role)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (message, phone_number, time, date, 'video/detection', 'image/detection', email, username, hospital, role))

    # Commit the transaction
    conn.commit()

    # Close the cursor and database connection
    cursor.close()
    conn.close()
    alert_message = message + " " + date + " " + time
    return redirect(url_for('home'))

@app.route('/edit_device/<int:device_id>', methods=['GET'])
@login_required
def edit_device(device_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices WHERE id = ?', (device_id,))
    device = cursor.fetchone()
    cursor.close()
    conn.close()
    stop_and_run_app()

    return render_template('device_edit.html', device=device)

@app.route('/update_device/<int:device_id>', methods=['POST'])
@login_required
def update_device(device_id):
    device_number = request.form['deviceNumber']
    room_number = request.form['roomNumber']
    ip_address = request.form['ipAddress']
    alert_setting = request.form.getlist('alertSetting')
    alert_settings_str = ', '.join(alert_setting)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE devices
        SET DeviceName = ?, RoomNumber = ?, IPAddress = ?, ModelSelection = ?
        WHERE id = ?
    ''', (device_number, room_number, ip_address, alert_settings_str, device_id))
    conn.commit()
    cursor.close()
    conn.close()
    stop_and_run_app()

    return redirect(url_for('home'))

@app.route('/delete_device/<int:device_id>', methods=['POST'])
@login_required
def delete_device(device_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM devices WHERE id = ?', (device_id,))
    conn.commit()
    cursor.close()
    conn.close()
    stop_and_run_app()

    return redirect(url_for('home'))

@app.route('/delete_alerts/<int:alerts_id>', methods=['POST'])
@login_required
def delete_alerts(alerts_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM alerts WHERE id = ?', (alerts_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('home'))

@app.route('/delete_staff/<int:staff_id>', methods=['POST'])
@login_required
def delete_staff(staff_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM staff WHERE staff_id = ?', (staff_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('home'))


BASE_IMAGE_DIR = r"events\images\detected"
BASE_VIDEO_DIR = r"events\videos"  # Update with correct path for videos

def read_directory(dir_path):
    result = {}
    for entry in os.listdir(dir_path):
        full_path = os.path.join(dir_path, entry)
        if os.path.isdir(full_path):
            result[entry] = read_directory(full_path)  # Recurse into subdirectory
        else:
            result[entry] = full_path  # Store file path
    return result

@app.route('/api/files/images')
def files_images():
    directory_structure = read_directory(BASE_IMAGE_DIR)
    return jsonify(directory_structure)

@app.route('/api/files/videos')
def files_videos():
    directory_structure = read_directory(BASE_VIDEO_DIR)
    return jsonify(directory_structure)

@app.route('/events/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(BASE_IMAGE_DIR, filename)

@app.route('/events/videos/<path:filename>')
def serve_video(filename):
    return send_from_directory(BASE_VIDEO_DIR, filename)


@app.route('/logout')
def logout():
    session.pop('email', None)
    session.pop('hospital',None)
    return redirect(url_for('login'))

@app.errorhandler(404)
def page_not_found(e):
    return "404 Not Found", 404

@app.errorhandler(500)
def internal_server_error(e):
    return f"Error loading the requested file: {e}", 500




outputFrames = {}
locks = {}

# Define the desired size for resizing
resize_width = 640
resize_height = 480

def generate(camera_index):
    global outputFrames, locks

    while True:
        if camera_index not in outputFrames or camera_index not in locks:
            continue

        with locks[camera_index]:
            frame = outputFrames[camera_index]
            if frame is None:
                continue

            # Resize the frame
            frame = cv2.resize(frame, (resize_width, resize_height))

            (flag, encodedImage) = cv2.imencode(".jpg", frame)
            if not flag:
                continue

        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
               bytearray(encodedImage) + b'\r\n')

@app.route("/video_feed/<int:camera_index>", methods=['POST', 'GET'])
def video_feed(camera_index):
    global outputFrames, locks

    if request.method == 'POST':
        # Retrieve the image from the POST request
        file = request.files['image']
        if file:
            img_np = np.frombuffer(file.read(), np.uint8)
            frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

            if camera_index not in locks:
                locks[camera_index] = threading.Lock()
                outputFrames[camera_index] = None

            with locks[camera_index]:
                # Resize the frame before storing it
                frame = cv2.resize(frame, (resize_width, resize_height))
                outputFrames[camera_index] = frame
            return jsonify({"status": "Frame received"}), 200

    # For GET requests, generate the video feed
    return Response(generate(camera_index),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

if __name__ == '__main__':

    # Run Flask app
    app.run(host='0.0.0.0', port=8000, debug=True, threaded=True, use_reloader=False)


from flask import Flask, render_template, request,  jsonify, session
import sqlite3
import speech_recognition as sr
r = sr.Recognizer()

import pygame
import time
from gtts import gTTS
from mutagen.mp3 import MP3

import speech_recognition as sr
import sounddevice as sd
import wave
import numpy as np
import threading
from dataset import Signup
from recognition import Signin

# ── Noise-robust voice engine (handles noisy environments + speaker ID) ───────
from voice_recognition_enhanced import (
    voice_to_text_enhanced,
    enroll_speaker,
    calibrate_noise,
    print_capability_report,
)
def month_name_to_number(month_name):
    # Create a dictionary mapping month names to their numbers
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, 
        "may": 5, "june": 6, "july": 7, "august": 8, 
        "september": 9, "october": 10, "november": 11, "december": 12
    }
    try:
        return months[month_name.lower()]
    except:
        return False

import inflect

# Create an instance of the inflect engine
p = inflect.engine()

def convert_to_number(input_str):
    try:
        # Handle ordinal numbers (e.g., "5th", "21st")
        if any(char.isdigit() for char in input_str):
            return int(p.ordinal_to_cardinal(input_str))
        else:
            # Handle written numbers (e.g., "one", "two")
            return int(p.number_to_words(input_str, andword="").strip())
    except:
        return input_str

connection = sqlite3.connect('database.db')
cursor = connection.cursor()

cursor.execute('create table if not exists user(Name TEXT, Phone TEXT, Email TEXT, password TEXT, Type TEXT)')

cursor.execute('create table if not exists tasks(Name TEXT, task TEXT, Date TEXT, Time TEXT)')

cursor.execute('create table if not exists blindtasks(Name TEXT, task TEXT, Date TEXT, Time TEXT)')

def text_to_speech(text1):
    print(text1)
    myobj = gTTS(text=text1, lang='en-us', tld='com', slow=False)
    myobj.save("voice.mp3")
    song = MP3("voice.mp3")
    pygame.mixer.init()
    pygame.mixer.music.load('voice.mp3')
    pygame.mixer.music.play()
    time.sleep(song.info.length)
    pygame.quit()

def voice_to_text(data):
    # Noise-robust replacement: uses spectral noise reduction + speaker verification
    username = None
    try:
        username = session.get('name')
    except RuntimeError:
        pass  # outside request context (e.g. Notification thread)

    result = voice_to_text_enhanced(
        prompt='say ' + data,
        tts_fn=text_to_speech,
        username=username,
        verify_speaker=(username is not None),
        max_retries=4,
    )
    return result if result else ""
def Notification():
    while True:
        from datetime import datetime

        # Connect to the SQLite database
        con = sqlite3.connect('database.db')
        cr = con.cursor()

        # Fetch current date and time (hour and minute only)
        now = datetime.now()
        current_date = now.date()

        f = open('sessionname.txt', 'r')
        name = f.read()
        f.close()
        # Fetch reminders for today
        cr.execute("SELECT * FROM blindtasks WHERE Date = ? and Name = ?", (current_date, name) )
        reminders = cr.fetchall()

        for reminder in reminders:
            name = reminder[0]
            task = reminder[1]
            reminder_date = reminder[2]
            reminder_time = reminder[3]

            from datetime import datetime
            now = datetime.now()

            current_hour_minute = now.strftime("%H:%M")

            current_hour_minute = current_hour_minute.split(':')

            hour = ''
            minute = ''
            if int(current_hour_minute[0])>12:
                hour = str(int(current_hour_minute[0]) - 12)
            else:
                hour = current_hour_minute[0]

            minute = current_hour_minute[1]

            current_time = hour+':'+minute
            
            print("Current Time =", current_time)
            print("Reminder Time =", reminder_time)
            
            # Check if it's time to send a reminder
            if current_time == reminder_time:
                msg = f"Reminder: task is {task} on {reminder_date} at {reminder_time}"
                text_to_speech(msg)
        time.sleep(1)

app = Flask(__name__)
app.secret_key = '\xf0?a\x9a\\\xff\xd4;\x0c\xcbHi'

@app.route('/')
def index():
    text_to_speech("Click anywhere to start")
    return render_template("index.html")

@app.route('/adminhome')
def adminhome():
    return render_template("adminlog.html")

@app.route('/adduser',  methods=['POST','GET'])
def adduser():
    if request.method == 'POST':
        Name = request.form['name']
        Phone = request.form['phone']
        Email = request.form['email']
        password = request.form['password']
        Type = 'blind'

        print(Name, Phone, Email, password, Type)

        Signup(Name)
        enroll_speaker(Name, tts_fn=text_to_speech)  # enroll voice profile

        msg = ['User details Saved for',
            'Name : ' + Name,
            'Phone : ' + Phone,
            'Email : ' + Email,
            'Password : ' + password,
            'Type : ' + Type]

        row = [Name, Phone, Email, password, Type]

        connection = sqlite3.connect('database.db')
        cursor = connection.cursor()

        cursor.execute('insert into user values(?,?,?,?,?)', row)
        connection.commit()

        return render_template("adminlog.html", msg=msg)
    return render_template("adminlog.html")

@app.route('/signup',  methods=['POST','GET'])
def signup():
    if request.method == 'POST':
        Name = request.form['name']
        Phone = request.form['phone']
        Email = request.form['email']
        password = request.form['password']
        Type = 'normal'

        print(Name, Phone, Email, password, Type)

        Signup(Name)
        enroll_speaker(Name, tts_fn=text_to_speech)  # enroll voice profile

        msg = ['User details Saved for',
            'Name : ' + Name,
            'Phone : ' + Phone,
            'Email : ' + Email,
            'Password : ' + password,
            'Type : ' + Type]

        row = [Name, Phone, Email, password, Type]

        connection = sqlite3.connect('database.db')
        cursor = connection.cursor()

        cursor.execute('insert into user values(?,?,?,?,?)', row)
        connection.commit()

        return render_template("normal.html", msg=msg)
    return render_template("normal.html")

@app.route('/addtask',  methods=['POST','GET'])
def addtask():
    connection = sqlite3.connect('database.db')
    cursor = connection.cursor()
    if request.method == 'POST':
        Name = session['name']
        Date = request.form['date']
        Time = request.form['time']
        task = request.form['task']

        print(Name, Date, Time, task)

        msg = ['Task Saved for',
            'Name : ' + Name,
            'Task : ' + task,
            'Date : ' + Date,
            'Time : ' + Time]

        row = [Name, task, Date, Time]

        cursor.execute('insert into tasks values(?,?,?,?)', row)
        connection.commit()

        cursor.execute("select * from tasks where name = '"+Name+"'")
        tasks = cursor.fetchall()
        return render_template("userlognormal.html", tasks=tasks, msg=msg)
    return render_template("userlognormal.html")

@app.route('/addtaskblind',  methods=['POST','GET'])
def addtaskblind():
    connection = sqlite3.connect('database.db')
    cursor = connection.cursor()
    if request.method == 'POST':
        Name = request.form['name']
        Date = request.form['date']
        Time = request.form['time']
        task = request.form['task']

        print(Name, Date, Time, task)

        msg = ['Task Saved for',
            'Name : ' + Name,
            'Task : ' + task,
            'Date : ' + Date,
            'Time : ' + Time]

        row = [Name, task, Date, Time]

        cursor.execute('insert into blindtasks values(?,?,?,?)', row)
        connection.commit()

        cursor.execute("select * from tasks where name = '"+Name+"'")
        tasks = cursor.fetchall()
        text_to_speech('task added successfully, click anywhare to add task')
        return render_template("addtask.html", tasks=tasks)
    
    cursor.execute("select * from user")
    names = cursor.fetchall()
    return render_template("addtask.html", names=names)

@app.route('/blindhome',  methods=['POST','GET'])
def blindhome():
    cursor.execute("select * from blindtasks where name = '"+Name+"'")
    tasks = cursor.fetchall()
    text_to_speech('logged in successfully, click anywhare to add task')

    return render_template("userlog.html", tasks=tasks)
                
@app.route('/signin',  methods=['POST','GET'])
def signin():
    if request.method == 'POST':
        Name = request.form['name']
        password = request.form['password']
        connection = sqlite3.connect('database.db')
        cursor = connection.cursor()

        cursor.execute("select * from user where name = '"+Name+"' and password = '"+password+"'")
        result = cursor.fetchone()

        if result:
            result = list(result)
            session['name'] = Name
            session['Type'] = result[-1]
            print(result)
            f = open('sessionname.txt', 'w')
            f.write(Name)
            f.close()
            if result[-1] == 'blind':
                res = Signin()
                if res == 'unknown':
                    text_to_speech("unknown person detection, Click anywhere to start")
                    return render_template("index.html")
                elif res == Name:
                    cursor.execute("select * from blindtasks where name = '"+Name+"'")
                    tasks = cursor.fetchall()
                    text_to_speech('logged in successfully, click anywhare to add task')
                    return render_template("userlog.html", tasks=tasks)
                else:
                    text_to_speech("face mismatched, Click anywhere to start")
                    return render_template("index.html")
            else:
                res = Signin()
                res = Name
                if res == 'unknown':
                    text_to_speech("unknown person detection")
                    return render_template("index.html")
                elif res == Name:
                    cursor.execute("select * from tasks where name = '"+Name+"'")
                    tasks = cursor.fetchall()
                    return render_template("userlognormal.html", tasks=tasks)
                else:
                    text_to_speech("face mismatched")
                    return render_template("index.html")
        else:
            text_to_speech("Click anywhere to start")
            return render_template("index.html")
    text_to_speech("Click anywhere to start")
    return render_template("index.html")

@app.route('/playtask')
def playtask():
    connection = sqlite3.connect('database.db')
    cursor = connection.cursor()
    cursor.execute("select * from tasks where name = '"+session['name']+"'")
    tasks = cursor.fetchall()
    if tasks:
        row = list(tasks[-1])
        msg = f'hi {row[0]}, you have task that {row[1]} on {row[2]} at {row[3]}'
        text_to_speech(msg)
    return jsonify('done')

@app.route('/admin',  methods=['POST','GET'])
def admin():
    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']

        if name == 'admin' and password == 'admin':
            return render_template("adminlog.html")
        else:
            return render_template("admin.html")
    return render_template("admin.html")

@app.route("/getename")
def getename():
    text = voice_to_text('say your name')
    global dd
    def email_format(sentence):
        sentence = sentence.replace(' ', '')
        return sentence
    def confirmation(text):
        global dd
        print('you said '+text)
        text_to_speech('you said '+text)
        text1 = voice_to_text('Say continue to confirm or say it again')
        if text1 == 'continue':
            dd = text
            return text
        else:
            text1 = email_format(text1)
            confirmation(text1)
    text = email_format(text)
    resp = confirmation(text)
    print('your name is ',dd)
    return jsonify(dd)

@app.route("/getpassword")
def getpassword():
    text = voice_to_text('password')
    def confirmation(text):
        global ddd
        print('you said '+text)
        text_to_speech('you said '+text)
        text1 = voice_to_text('Say continue to confirm or say it again')
        if text1 == 'continue':
            ddd = text
            return text
        else:
            confirmation(text1)
    resp = confirmation(text)
    print('password is ',ddd)
    return jsonify(ddd)

@app.route("/gettask")
def gettask():
    text = voice_to_text('say your task')
    print('your task is ',text)
    text_to_speech('you said '+text)
    session['task'] = text
    return jsonify(text)


@app.route("/getdate")
def getdate():
    Date = None
    while True:
        text = voice_to_text('say date')
        text = text.split()
        print(text)
        if len(text) == 3:
            year = text[0]
            month_name = text[1]
            month = month_name_to_number(month_name)
            day_str = text[2]
            day = convert_to_number(day_str)
            print(day, month, day)
            if year and month and day:
                print(year, month, day)
                Date = str(year)+'-'+str(month)+'-'+str(day)
                print(Date)
            break
    session['date'] = Date
    return jsonify(Date)

@app.route("/gettime")
def gettime():
    Time1 = None
    while True:
        Time = voice_to_text('say time')
        Time = Time.replace(' ', '')
        Time = Time.replace('.', '')
        Time = Time.replace('p', '')
        Time = Time.replace('a', '')
        Time = Time.replace('m', '')
        Time = Time.split(':')
        
        if len(Time) == 2:
            session['time'] = str(Time[0])+':'+str(Time[1])
            break
    return jsonify(Time)


@app.route('/addtaskblindperson')
def addtaskblindperson():
    connection = sqlite3.connect('database.db')
    cursor = connection.cursor()
    Name = session['name']
    Date = session['date']
    Time = session['time']
    task = session['task']

    print(Name, Date, Time, task)

    msg = ['Task Saved for',
        'Name : ' + Name,
        'Task : ' + task,
        'Date : ' + Date,
        'Time : ' + Time]

    row = [Name, task, Date, Time]

    cursor.execute('insert into blindtasks values(?,?,?,?)', row)
    connection.commit()

    cursor.execute("select * from tasks where name = '"+Name+"'")
    tasks = cursor.fetchall()
    text_to_speech('task added successfully, click anywhare to add task')
    return jsonify("task added successfully")

@app.route('/logout')
def logout():
    return render_template('index.html')
   
if __name__ == "__main__":
    print_capability_report()
    print("[App] Calibrating ambient noise for 1.5 seconds, please stay quiet...")
    calibrate_noise()
    t1 = threading.Thread(target=Notification, daemon=True)
    t1.start()
    app.run(debug=True, use_reloader=False)

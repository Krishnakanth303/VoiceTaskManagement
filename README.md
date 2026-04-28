# 🎙️ Voice Task Management System

A voice-controlled task management web application built with Flask, featuring face recognition-based authentication and speech-to-text task creation.

---

## 🚀 Features

- 🎤 **Voice-controlled task creation** — speak your tasks instead of typing them
- 👤 **Face recognition login** — authenticate users via webcam using FaceNet
- 🔐 **Admin & User roles** — separate dashboards and permissions
- 📋 **Task dashboard** — view, manage, and track tasks in real time
- 🗄️ **SQLite database** — lightweight local storage for tasks and users
- 🌐 **Flask web app** — runs locally in your browser

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript |
| Voice Recognition | SpeechRecognition, PyAudio |
| Face Recognition | FaceNet (TensorFlow), OpenCV |
| Database | SQLite |
| ML Models | scikit-learn, scipy, numpy |

---

## 📁 Project Structure

```
VoiceTaskManagement/
├── app.py                        # Main Flask application
├── voice_recognition_enhanced.py # Voice input processing
├── recognition.py                # Face recognition logic
├── detect_and_align.py           # Face detection & alignment
├── dataset.py                    # Dataset handling for face training
├── requirements.txt              # Python dependencies
├── det1.npy / det2.npy / det3.npy # MTCNN detection model weights
├── static/
│   ├── css/                      # Stylesheets
│   └── js/                       # JavaScript files
└── templates/
    ├── index.html                # Landing page
    ├── admin.html                # Admin dashboard
    ├── adminlog.html             # Admin login
    ├── userlog.html              # User login
    ├── normal.html               # User dashboard
    ├── addtask.html              # Add task page
    └── userlognormal.html        # User session page
```

---

## ⚙️ Installation

### Prerequisites
- Python 3.10
- Webcam (for face recognition)
- Microphone (for voice input)

### Steps

**1. Clone the repository:**
```bash
git clone https://github.com/Krishnakanth303/VoiceTaskManagement.git
cd VoiceTaskManagement
```

**2. Create and activate a virtual environment:**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Download the FaceNet model:**

Download `20170512-110547.pb` from [FaceNet releases](https://github.com/davidsandberg/facenet) and place it in a folder named `20170512-110547/` at the project root.

**5. Run the app:**
```bash
python app.py
```

**6. Open your browser:**
```
http://localhost:5000
```

---

## 🧑‍💻 Usage

1. **Register** your face using the dataset collection feature
2. **Log in** via face recognition through your webcam
3. **Add tasks** by clicking the mic button and speaking your task
4. **Admin** can view and manage all users and tasks from the admin dashboard

---

## 📦 Key Dependencies

```
Flask
SpeechRecognition
PyAudio
opencv-python
tensorflow
scikit-learn
scipy
numpy
pygame
```

Install all at once via:
```bash
pip install -r requirements.txt
```

---

## ⚠️ Notes

- The FaceNet model file (`20170512-110547.pb`, ~90MB) is **not included** in this repo due to GitHub's file size limits. Download it separately as described above.
- Make sure your browser has permission to access the **microphone** and **webcam**.
- Tested on **Windows 10/11** with Python 3.10.

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 🙋‍♂️ Author

**Krishnakanth303** — [GitHub Profile](https://github.com/Krishnakanth303)

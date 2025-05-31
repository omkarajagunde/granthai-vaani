import os
import asyncio
import sqlite3
from datetime import datetime, timedelta
import json
import speech_recognition as sr
import requests
from io import BytesIO
import pygame
from dotenv import load_dotenv
from typing import Dict, List, Optional, Tuple

# Load environment variables
load_dotenv()

class DatabaseManager:
    def __init__(self, db_path="hospital.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create doctors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_name TEXT NOT NULL,
                specialization TEXT,
                time_slot TEXT NOT NULL,
                status TEXT DEFAULT 'available'
            )
        ''')
        
        # Create tests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_name TEXT NOT NULL,
                price REAL NOT NULL,
                duration_minutes INTEGER DEFAULT 30
            )
        ''')
        
        # Create appointments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                patient_phone TEXT,
                appointment_type TEXT NOT NULL,
                doctor_name TEXT,
                test_name TEXT,
                appointment_time TEXT NOT NULL,
                status TEXT DEFAULT 'confirmed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert sample data if tables are empty
        cursor.execute("SELECT COUNT(*) FROM doctors")
        if cursor.fetchone()[0] == 0:
            sample_doctors = [
                ("Dr. Smith", "Cardiology", "09:00", "available"),
                ("Dr. Smith", "Cardiology", "10:00", "available"),
                ("Dr. Smith", "Cardiology", "11:00", "unavailable"),
                ("Dr. Johnson", "Neurology", "09:30", "available"),
                ("Dr. Johnson", "Neurology", "10:30", "available"),
                ("Dr. Patel", "General Medicine", "14:00", "available"),
                ("Dr. Patel", "General Medicine", "15:00", "available")
            ]
            cursor.executemany(
                "INSERT INTO doctors (doctor_name, specialization, time_slot, status) VALUES (?, ?, ?, ?)",
                sample_doctors
            )
        
        cursor.execute("SELECT COUNT(*) FROM tests")
        if cursor.fetchone()[0] == 0:
            sample_tests = [
                ("Blood Test", 50.0, 30),
                ("X-Ray", 100.0, 20),
                ("MRI Scan", 500.0, 60),
                ("CT Scan", 300.0, 45),
                ("ECG", 75.0, 15),
                ("Ultrasound", 150.0, 30)
            ]
            cursor.executemany(
                "INSERT INTO tests (test_name, price, duration_minutes) VALUES (?, ?, ?)",
                sample_tests
            )
        
        conn.commit()
        conn.close()
    
    def get_available_doctors(self) -> List[Dict]:
        """Get list of available doctors and their time slots"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT doctor_name, specialization, time_slot 
            FROM doctors 
            WHERE status = 'available'
            ORDER BY doctor_name, time_slot
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        doctors = []
        for row in results:
            doctors.append({
                "doctor_name": row[0],
                "specialization": row[1],
                "time_slot": row[2]
            })
        
        return doctors
    
    def get_available_tests(self) -> List[Dict]:
        """Get list of available tests and their prices"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT test_name, price FROM tests ORDER BY test_name")
        results = cursor.fetchall()
        conn.close()
        
        tests = []
        for row in results:
            tests.append({
                "test_name": row[0],
                "price": row[1]
            })
        
        return tests
    
    def book_appointment(self, patient_name: str, patient_phone: str, 
                        appointment_type: str, doctor_name: str = None, 
                        test_name: str = None, appointment_time: str = None) -> bool:
        """Book an appointment and update database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Insert appointment
            cursor.execute('''
                INSERT INTO appointments 
                (patient_name, patient_phone, appointment_type, doctor_name, test_name, appointment_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (patient_name, patient_phone, appointment_type, doctor_name, test_name, appointment_time))
            
            # If doctor appointment, mark time slot as unavailable
            if appointment_type == "doctor" and doctor_name and appointment_time:
                cursor.execute('''
                    UPDATE doctors 
                    SET status = 'unavailable' 
                    WHERE doctor_name = ? AND time_slot = ?
                ''', (doctor_name, appointment_time))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error booking appointment: {e}")
            return False
        finally:
            conn.close()

class ElevenLabsClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
    
    def text_to_speech(self, text: str) -> bytes:
        """Convert text to speech using ElevenLabs API"""
        url = f"{self.base_url}/text-to-speech/{self.voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 200:
            return response.content
        else:
            print(f"Error with ElevenLabs API: {response.status_code}")
            return None

class SpeechManager:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        pygame.mixer.init()
        
        # Adjust for ambient noise
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
    
    def listen_for_speech(self, timeout: int = 10) -> Optional[str]:
        """Listen for speech input and convert to text"""
        try:
            with self.microphone as source:
                print("Listening...")
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
            
            print("Processing speech...")
            text = self.recognizer.recognize_google(audio)
            print(f"You said: {text}")
            return text
        
        except sr.WaitTimeoutError:
            print("No speech detected within timeout period")
            return None
        except sr.UnknownValueError:
            print("Could not understand the speech")
            return None
        except sr.RequestError as e:
            print(f"Error with speech recognition service: {e}")
            return None
    
    def play_audio(self, audio_data: bytes):
        """Play audio using pygame"""
        if audio_data:
            audio_file = BytesIO(audio_data)
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)

class HospitalReceptionistAgent:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.elevenlabs_client = ElevenLabsClient(os.getenv("ELEVENLABS_API_KEY"))
        self.speech_manager = SpeechManager()
        
        # Conversation state
        self.conversation_state = {
            "stage": "greeting",
            "patient_name": None,
            "patient_phone": None,
            "appointment_type": None,
            "selected_doctor": None,
            "selected_test": None,
            "selected_time": None
        }
        
        # System prompt for the AI
        self.system_prompt = """
You are a friendly and professional hospital receptionist AI assistant. Your job is to help patients book appointments for either doctor consultations or medical tests.

Guidelines:
1. Always be polite, empathetic, and professional
2. Speak clearly and at a moderate pace
3. Ask one question at a time to avoid overwhelming the patient
4. Confirm important details before finalizing bookings
5. Provide clear information about available options
6. If you don't understand something, politely ask for clarification
7. Keep responses concise but informative
8. Show empathy for patients' health concerns

Your conversation flow should be:
1. Greet the patient warmly
2. Ask what service they need (doctor appointment or medical test)
3. Collect patient information (name, phone)
4. Show available options based on their choice
5. Help them select and confirm their appointment
6. Provide confirmation details

Remember to be patient and understanding, as some patients may be anxious about their health.
"""
    
    def speak(self, text: str):
        """Convert text to speech and play it"""
        print(f"AI: {text}")
        audio_data = self.elevenlabs_client.text_to_speech(text)
        if audio_data:
            self.speech_manager.play_audio(audio_data)
    
    def listen(self) -> Optional[str]:
        """Listen for patient input"""
        return self.speech_manager.listen_for_speech()
    
    def process_user_input(self, user_input: str) -> str:
        """Process user input and generate appropriate response"""
        user_input = user_input.lower().strip()
        
        if self.conversation_state["stage"] == "greeting":
            return self.handle_greeting(user_input)
        elif self.conversation_state["stage"] == "service_selection":
            return self.handle_service_selection(user_input)
        elif self.conversation_state["stage"] == "patient_info":
            return self.handle_patient_info(user_input)
        elif self.conversation_state["stage"] == "doctor_selection":
            return self.handle_doctor_selection(user_input)
        elif self.conversation_state["stage"] == "test_selection":
            return self.handle_test_selection(user_input)
        elif self.conversation_state["stage"] == "confirmation":
            return self.handle_confirmation(user_input)
        else:
            return "I'm sorry, I didn't understand. Could you please repeat that?"
    
    def handle_greeting(self, user_input: str) -> str:
        self.conversation_state["stage"] = "service_selection"
        return "Hello! Welcome to our hospital. I'm here to help you book an appointment. Would you like to schedule a consultation with a doctor or book a medical test?"
    
    def handle_service_selection(self, user_input: str) -> str:
        if "doctor" in user_input or "consultation" in user_input or "consult" in user_input:
            self.conversation_state["appointment_type"] = "doctor"
            self.conversation_state["stage"] = "patient_info"
            return "Great! I'll help you book a doctor consultation. May I have your full name, please?"
        elif "test" in user_input or "lab" in user_input or "scan" in user_input:
            self.conversation_state["appointment_type"] = "test"
            self.conversation_state["stage"] = "patient_info"
            return "Perfect! I'll help you book a medical test. May I have your full name, please?"
        else:
            return "I can help you with either a doctor consultation or medical tests. Could you please specify which service you need?"
    
    def handle_patient_info(self, user_input: str) -> str:
        if not self.conversation_state["patient_name"]:
            self.conversation_state["patient_name"] = user_input.title()
            return f"Thank you, {self.conversation_state['patient_name']}. Could you please provide your phone number?"
        else:
            # Extract phone number (simple validation)
            phone = ''.join(filter(str.isdigit, user_input))
            if len(phone) >= 10:
                self.conversation_state["patient_phone"] = phone
                if self.conversation_state["appointment_type"] == "doctor":
                    self.conversation_state["stage"] = "doctor_selection"
                    return self.show_available_doctors()
                else:
                    self.conversation_state["stage"] = "test_selection"
                    return self.show_available_tests()
            else:
                return "I need a valid phone number. Could you please provide your 10-digit phone number?"
    
    def show_available_doctors(self) -> str:
        doctors = self.db_manager.get_available_doctors()
        if not doctors:
            return "I'm sorry, but there are no available doctor appointments at the moment. Would you like me to help you with something else?"
        
        # Group by doctor
        doctor_info = {}
        for doc in doctors:
            name = doc["doctor_name"]
            if name not in doctor_info:
                doctor_info[name] = {"specialization": doc["specialization"], "slots": []}
            doctor_info[name]["slots"].append(doc["time_slot"])
        
        response = "Here are our available doctors and their time slots:\n\n"
        for name, info in doctor_info.items():
            response += f"{name} ({info['specialization']}): {', '.join(info['slots'])}\n"
        
        response += "\nWhich doctor and time slot would you prefer?"
        return response
    
    def show_available_tests(self) -> str:
        tests = self.db_manager.get_available_tests()
        if not tests:
            return "I'm sorry, but there are no available tests at the moment."
        
        response = "Here are our available medical tests:\n\n"
        for test in tests:
            response += f"{test['test_name']}: ₹{test['price']}\n"
        
        response += "\nWhich test would you like to book?"
        return response
    
    def handle_doctor_selection(self, user_input: str) -> str:
        doctors = self.db_manager.get_available_doctors()
        
        # Simple matching logic - look for doctor name and time in input
        selected_doctor = None
        selected_time = None
        
        for doc in doctors:
            doc_name_parts = doc["doctor_name"].lower().split()
            if any(part in user_input for part in doc_name_parts):
                if doc["time_slot"] in user_input or doc["time_slot"].replace(":", "") in user_input:
                    selected_doctor = doc["doctor_name"]
                    selected_time = doc["time_slot"]
                    break
        
        if selected_doctor and selected_time:
            self.conversation_state["selected_doctor"] = selected_doctor
            self.conversation_state["selected_time"] = selected_time
            self.conversation_state["stage"] = "confirmation"
            
            return f"Perfect! I have you scheduled with {selected_doctor} at {selected_time}. Let me confirm your details:\n\nName: {self.conversation_state['patient_name']}\nPhone: {self.conversation_state['patient_phone']}\nDoctor: {selected_doctor}\nTime: {selected_time}\n\nShall I confirm this appointment?"
        else:
            return "I couldn't identify the doctor and time from your response. Could you please specify the doctor's name and preferred time slot? For example, 'Dr. Smith at 9:00' or 'Dr. Johnson at 10:30'."
    
    def handle_test_selection(self, user_input: str) -> str:
        tests = self.db_manager.get_available_tests()
        
        # Simple matching logic
        selected_test = None
        for test in tests:
            if test["test_name"].lower() in user_input:
                selected_test = test
                break
        
        if selected_test:
            self.conversation_state["selected_test"] = selected_test["test_name"]
            self.conversation_state["stage"] = "confirmation"
            
            return f"Great! I have you scheduled for a {selected_test['test_name']} at ₹{selected_test['price']}. Let me confirm your details:\n\nName: {self.conversation_state['patient_name']}\nPhone: {self.conversation_state['patient_phone']}\nTest: {selected_test['test_name']}\nPrice: ₹{selected_test['price']}\n\nShall I confirm this appointment?"
        else:
            return "I couldn't identify the test from your response. Could you please specify which test you'd like to book from the list I provided?"
    
    def handle_confirmation(self, user_input: str) -> str:
        if "yes" in user_input or "confirm" in user_input or "ok" in user_input or "sure" in user_input:
            # Book the appointment
            success = self.db_manager.book_appointment(
                patient_name=self.conversation_state["patient_name"],
                patient_phone=self.conversation_state["patient_phone"],
                appointment_type=self.conversation_state["appointment_type"],
                doctor_name=self.conversation_state["selected_doctor"],
                test_name=self.conversation_state["selected_test"],
                appointment_time=self.conversation_state["selected_time"]
            )
            
            if success:
                response = "Excellent! Your appointment has been confirmed. "
                if self.conversation_state["appointment_type"] == "doctor":
                    response += f"Please arrive 15 minutes early for your appointment with {self.conversation_state['selected_doctor']} at {self.conversation_state['selected_time']}."
                else:
                    response += f"Please arrive 15 minutes early for your {self.conversation_state['selected_test']} test."
                
                response += " Is there anything else I can help you with today?"
                
                # Reset conversation state
                self.conversation_state = {
                    "stage": "greeting",
                    "patient_name": None,
                    "patient_phone": None,
                    "appointment_type": None,
                    "selected_doctor": None,
                    "selected_test": None,
                    "selected_time": None
                }
                
                return response
            else:
                return "I'm sorry, there was an error booking your appointment. Please try again or contact our staff directly."
        else:
            return "No problem! Would you like to make any changes to your appointment details, or is there something else I can help you with?"
    
    def run(self):
        """Main conversation loop"""
        print("Hospital Receptionist AI Agent Started!")
        print("Say 'hello' or 'hi' to start the conversation.")
        print("Say 'quit' or 'exit' to end the conversation.\n")
        
        # Initial greeting
        greeting = "Hello! Welcome to our hospital. I'm your AI assistant. How can I help you today?"
        self.speak(greeting)
        
        while True:
            user_input = self.listen()
            
            if user_input is None:
                self.speak("I didn't catch that. Could you please repeat?")
                continue
            
            if user_input.lower() in ["quit", "exit", "goodbye", "bye"]:
                farewell = "Thank you for choosing our hospital. Have a great day and take care!"
                self.speak(farewell)
                break
            
            response = self.process_user_input(user_input)
            self.speak(response)

# Main execution
if __name__ == "__main__":
    # Check if required packages are installed
    required_packages = ["speech_recognition", "pygame", "requests", "python-dotenv"]
    
    print("Hospital Receptionist AI Agent")
    print("=" * 40)
  
    try:
        agent = HospitalReceptionistAgent()
        agent.run()
    except KeyboardInterrupt:
        print("\nAgent stopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        print("Please make sure all requirements are met and try again.")
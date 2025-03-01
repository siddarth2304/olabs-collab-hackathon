from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit, join_room
import ollama
from fpdf import FPDF
from deep_translator import GoogleTranslator
import subprocess
import os
from textblob import TextBlob
import logging
import json
import re
import requests
import random
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Store active rooms and users
active_rooms = {}
cursor_positions = {}
code_sessions = {}
groups = {}
leaderboard = {}
used_questions = {}  # {username: {class_subject: set of used question IDs}}

# QuizAPI.io API key (replace with your actual key if available)
QUIZAPI_KEY = "h5U3DJJ2f4jwF40C4QX828w4wcgyheoxfdpUzkH2"

# Supported languages for code execution
SUPPORTED_LANGUAGES = ["python", "javascript", "java", "cpp"]

# Mapping class and subject to QuizAPI.io difficulty/categories
CLASS_DIFFICULTY_MAP = {
    "Class 6": "Easy",
    "Class 7": "Easy",
    "Class 8": "Easy",
    "Class 9": "Medium",
    "Class 10": "Medium"
}

SUBJECT_CATEGORY_MAP = {
    "physics": "science",
    "chemistry": "science",
    "biology": "science",
    "math": "maths"
}

# Fallback questions (10 per class-subject combo)
FALLBACK_QUESTIONS = {
    "Class 6": {
        "physics": [
            {"id": "f1", "question": "What is the main source of energy on Earth?", "options": ["Sun", "Moon", "Wind", "Water"], "answer": "Sun"},
            {"id": "f2", "question": "What do we call a push or pull?", "options": ["Force", "Energy", "Heat", "Light"], "answer": "Force"},
            {"id": "f3", "question": "What is the unit of length?", "options": ["Meter", "Kilogram", "Second", "Liter"], "answer": "Meter"},
            {"id": "f4", "question": "What causes shadows?", "options": ["Light", "Sound", "Heat", "Air"], "answer": "Light"},
            {"id": "f5", "question": "What is the boiling point of water?", "options": ["100°C", "0°C", "50°C", "200°C"], "answer": "100°C"},
            {"id": "f6", "question": "What is the freezing point of water?", "options": ["0°C", "100°C", "-10°C", "50°C"], "answer": "0°C"},
            {"id": "f7", "question": "What is sound caused by?", "options": ["Vibrations", "Light", "Heat", "Gravity"], "answer": "Vibrations"},
            {"id": "f8", "question": "What is the SI unit of time?", "options": ["Second", "Minute", "Hour", "Day"], "answer": "Second"},
            {"id": "f9", "question": "What helps us see objects?", "options": ["Light", "Sound", "Air", "Water"], "answer": "Light"},
            {"id": "f10", "question": "What is the Earth’s shape?", "options": ["Sphere", "Flat", "Square", "Cube"], "answer": "Sphere"}
        ],
        "chemistry": [
            {"id": "f11", "question": "What is water made of?", "options": ["H₂O", "CO₂", "O₂", "N₂"], "answer": "H₂O"},
            {"id": "f12", "question": "What gas do we breathe?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Helium"], "answer": "Oxygen"},
            {"id": "f13", "question": "What is the solid form of water?", "options": ["Ice", "Steam", "Liquid", "Gas"], "answer": "Ice"},
            {"id": "f14", "question": "What is table salt’s common name?", "options": ["Sodium Chloride", "Sugar", "Pepper", "Baking Soda"], "answer": "Sodium Chloride"},
            {"id": "f15", "question": "What gas helps things burn?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Hydrogen"], "answer": "Oxygen"},
            {"id": "f16", "question": "What is the liquid form of water?", "options": ["Water", "Ice", "Steam", "Snow"], "answer": "Water"},
            {"id": "f17", "question": "What is rust made from?", "options": ["Iron Oxide", "Copper", "Silver", "Gold"], "answer": "Iron Oxide"},
            {"id": "f18", "question": "What gas do plants release?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Helium"], "answer": "Oxygen"},
            {"id": "f19", "question": "What is sugar an example of?", "options": ["Carbohydrate", "Protein", "Fat", "Vitamin"], "answer": "Carbohydrate"},
            {"id": "f20", "question": "What turns litmus paper red?", "options": ["Acid", "Base", "Salt", "Water"], "answer": "Acid"}
        ],
        "biology": [
            {"id": "f21", "question": "What do plants need to make food?", "options": ["Sunlight", "Darkness", "Sound", "Heat"], "answer": "Sunlight"},
            {"id": "f22", "question": "What is the largest organ in the human body?", "options": ["Skin", "Heart", "Brain", "Lungs"], "answer": "Skin"},
            {"id": "f23", "question": "What gas do plants use?", "options": ["Carbon Dioxide", "Oxygen", "Nitrogen", "Helium"], "answer": "Carbon Dioxide"},
            {"id": "f24", "question": "What carries oxygen in blood?", "options": ["Red Blood Cells", "White Blood Cells", "Platelets", "Plasma"], "answer": "Red Blood Cells"},
            {"id": "f25", "question": "What is the process of making food in plants?", "options": ["Photosynthesis", "Respiration", "Digestion", "Circulation"], "answer": "Photosynthesis"},
            {"id": "f26", "question": "What is the human body’s control center?", "options": ["Brain", "Heart", "Lungs", "Stomach"], "answer": "Brain"},
            {"id": "f27", "question": "What do animals breathe out?", "options": ["Carbon Dioxide", "Oxygen", "Nitrogen", "Helium"], "answer": "Carbon Dioxide"},
            {"id": "f28", "question": "What is the basic unit of life?", "options": ["Cell", "Atom", "Molecule", "Tissue"], "answer": "Cell"},
            {"id": "f29", "question": "What pumps blood in the body?", "options": ["Heart", "Lungs", "Brain", "Liver"], "answer": "Heart"},
            {"id": "f30", "question": "What do leaves use to make food?", "options": ["Chlorophyll", "Sugar", "Water", "Soil"], "answer": "Chlorophyll"}
        ],
        "math": [
            {"id": "f31", "question": "What is 5 + 3?", "options": ["8", "7", "9", "6"], "answer": "8"},
            {"id": "f32", "question": "What is 10 - 4?", "options": ["6", "5", "7", "8"], "answer": "6"},
            {"id": "f33", "question": "What is 2 × 3?", "options": ["6", "5", "4", "8"], "answer": "6"},
            {"id": "f34", "question": "What is 8 ÷ 2?", "options": ["4", "3", "5", "2"], "answer": "4"},
            {"id": "f35", "question": "What is 7 + 6?", "options": ["13", "12", "14", "11"], "answer": "13"},
            {"id": "f36", "question": "What is 9 - 5?", "options": ["4", "3", "5", "6"], "answer": "4"},
            {"id": "f37", "question": "What is 4 × 4?", "options": ["16", "12", "20", "8"], "answer": "16"},
            {"id": "f38", "question": "What is 15 ÷ 3?", "options": ["5", "4", "6", "3"], "answer": "5"},
            {"id": "f39", "question": "What is 10 + 2?", "options": ["12", "11", "13", "10"], "answer": "12"},
            {"id": "f40", "question": "What is 6 - 3?", "options": ["3", "2", "4", "5"], "answer": "3"}
        ]
    },
    "Class 7": {
        "physics": [
            {"id": "f41", "question": "What is the unit of speed?", "options": ["m/s", "kg", "m", "J"], "answer": "m/s"},
            {"id": "f42", "question": "What reflects light?", "options": ["Mirror", "Wall", "Water", "Air"], "answer": "Mirror"},
            {"id": "f43", "question": "What is the SI unit of mass?", "options": ["Kilogram", "Meter", "Second", "Liter"], "answer": "Kilogram"},
            {"id": "f44", "question": "What is heat a form of?", "options": ["Energy", "Force", "Light", "Sound"], "answer": "Energy"},
            {"id": "f45", "question": "What makes sound louder?", "options": ["Amplitude", "Frequency", "Wavelength", "Speed"], "answer": "Amplitude"},
            {"id": "f46", "question": "What is the Earth’s main axis tilt?", "options": ["23.5°", "90°", "45°", "0°"], "answer": "23.5°"},
            {"id": "f47", "question": "What is the unit of temperature?", "options": ["Celsius", "Meter", "Kilogram", "Second"], "answer": "Celsius"},
            {"id": "f48", "question": "What bends light?", "options": ["Lens", "Mirror", "Wall", "Air"], "answer": "Lens"},
            {"id": "f49", "question": "What is the speed of sound in air (approx)?", "options": ["340 m/s", "300 m/s", "400 m/s", "500 m/s"], "answer": "340 m/s"},
            {"id": "f50", "question": "What is the Earth’s largest layer?", "options": ["Mantle", "Crust", "Core", "Atmosphere"], "answer": "Mantle"}
        ],
        "chemistry": [
            {"id": "f51", "question": "What gas is used in balloons?", "options": ["Helium", "Oxygen", "Nitrogen", "Carbon Dioxide"], "answer": "Helium"},
            {"id": "f52", "question": "What is the symbol for oxygen?", "options": ["O", "H", "C", "N"], "answer": "O"},
            {"id": "f53", "question": "What turns blue litmus red?", "options": ["Acid", "Base", "Salt", "Water"], "answer": "Acid"},
            {"id": "f54", "question": "What is the symbol for hydrogen?", "options": ["H", "O", "C", "N"], "answer": "H"},
            {"id": "f55", "question": "What gas is produced by burning?", "options": ["Carbon Dioxide", "Oxygen", "Nitrogen", "Helium"], "answer": "Carbon Dioxide"},
            {"id": "f56", "question": "What is vinegar an example of?", "options": ["Acid", "Base", "Salt", "Sugar"], "answer": "Acid"},
            {"id": "f57", "question": "What is baking soda?", "options": ["Sodium Bicarbonate", "Sugar", "Salt", "Flour"], "answer": "Sodium Bicarbonate"},
            {"id": "f58", "question": "What gas makes up most of the air?", "options": ["Nitrogen", "Oxygen", "Carbon Dioxide", "Helium"], "answer": "Nitrogen"},
            {"id": "f59", "question": "What is the symbol for carbon?", "options": ["C", "H", "O", "N"], "answer": "C"},
            {"id": "f60", "question": "What is lime water?", "options": ["Calcium Hydroxide", "Sugar Water", "Salt Water", "Acid"], "answer": "Calcium Hydroxide"}
        ],
        "biology": [
            {"id": "f61", "question": "What do animals need to breathe?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Helium"], "answer": "Oxygen"},
            {"id": "f62", "question": "What organ helps us breathe?", "options": ["Lungs", "Heart", "Brain", "Stomach"], "answer": "Lungs"},
            {"id": "f63", "question": "What is the green part of a plant?", "options": ["Leaf", "Root", "Stem", "Flower"], "answer": "Leaf"},
            {"id": "f64", "question": "What do roots absorb?", "options": ["Water", "Air", "Light", "Sound"], "answer": "Water"},
            {"id": "f65", "question": "What is the food factory of a plant?", "options": ["Leaf", "Root", "Stem", "Flower"], "answer": "Leaf"},
            {"id": "f66", "question": "What do humans exhale?", "options": ["Carbon Dioxide", "Oxygen", "Nitrogen", "Helium"], "answer": "Carbon Dioxide"},
            {"id": "f67", "question": "What is the main job of the heart?", "options": ["Pumping blood", "Breathing", "Digesting", "Thinking"], "answer": "Pumping blood"},
            {"id": "f68", "question": "What protects the human body?", "options": ["Skin", "Hair", "Nails", "Eyes"], "answer": "Skin"},
            {"id": "f69", "question": "What helps plants grow tall?", "options": ["Stem", "Leaf", "Root", "Flower"], "answer": "Stem"},
            {"id": "f70", "question": "What do fish use to breathe?", "options": ["Gills", "Lungs", "Skin", "Nose"], "answer": "Gills"}
        ],
        "math": [
            {"id": "f71", "question": "What is 6 + 4?", "options": ["10", "9", "11", "8"], "answer": "10"},
            {"id": "f72", "question": "What is 12 - 5?", "options": ["7", "6", "8", "9"], "answer": "7"},
            {"id": "f73", "question": "What is 3 × 4?", "options": ["12", "10", "14", "8"], "answer": "12"},
            {"id": "f74", "question": "What is 16 ÷ 4?", "options": ["4", "3", "5", "2"], "answer": "4"},
            {"id": "f75", "question": "What is 8 + 7?", "options": ["15", "14", "16", "13"], "answer": "15"},
            {"id": "f76", "question": "What is 10 - 6?", "options": ["4", "3", "5", "2"], "answer": "4"},
            {"id": "f77", "question": "What is 5 × 3?", "options": ["15", "12", "18", "10"], "answer": "15"},
            {"id": "f78", "question": "What is 20 ÷ 5?", "options": ["4", "3", "5", "6"], "answer": "4"},
            {"id": "f79", "question": "What is 9 + 2?", "options": ["11", "10", "12", "13"], "answer": "11"},
            {"id": "f80", "question": "What is 15 - 7?", "options": ["8", "7", "9", "6"], "answer": "8"}
        ]
    },
    "Class 8": {
        "physics": [
            {"id": "f81", "question": "What is the unit of pressure?", "options": ["Pascal", "Newton", "Joule", "Watt"], "answer": "Pascal"},
            {"id": "f82", "question": "What causes friction?", "options": ["Roughness", "Smoothness", "Light", "Sound"], "answer": "Roughness"},
            {"id": "f83", "question": "What is the unit of electric current?", "options": ["Ampere", "Volt", "Ohm", "Watt"], "answer": "Ampere"},
            {"id": "f84", "question": "What is the speed of sound in air?", "options": ["340 m/s", "300 m/s", "400 m/s", "500 m/s"], "answer": "340 m/s"},
            {"id": "f85", "question": "What reflects sound?", "options": ["Echo", "Light", "Heat", "Wind"], "answer": "Echo"},
            {"id": "f86", "question": "What is the unit of energy?", "options": ["Joule", "Newton", "Watt", "Pascal"], "answer": "Joule"},
            {"id": "f87", "question": "What is the Earth’s gravitational pull?", "options": ["9.8 m/s²", "10 m/s²", "8 m/s²", "12 m/s²"], "answer": "9.8 m/s²"},
            {"id": "f88", "question": "What is light made of?", "options": ["Photons", "Electrons", "Protons", "Neutrons"], "answer": "Photons"},
            {"id": "f89", "question": "What is the unit of power?", "options": ["Watt", "Joule", "Newton", "Volt"], "answer": "Watt"},
            {"id": "f90", "question": "What is the main source of light?", "options": ["Sun", "Moon", "Stars", "Fire"], "answer": "Sun"}
        ],
        "chemistry": [
            {"id": "f91", "question": "What is the symbol for gold?", "options": ["Au", "Ag", "Fe", "Cu"], "answer": "Au"},
            {"id": "f92", "question": "What gas is in soda?", "options": ["Carbon Dioxide", "Oxygen", "Nitrogen", "Helium"], "answer": "Carbon Dioxide"},
            {"id": "f93", "question": "What is the symbol for iron?", "options": ["Fe", "Au", "Ag", "Cu"], "answer": "Fe"},
            {"id": "f94", "question": "What is a mixture of metals called?", "options": ["Alloy", "Compound", "Element", "Solution"], "answer": "Alloy"},
            {"id": "f95", "question": "What gas is flammable?", "options": ["Hydrogen", "Oxygen", "Nitrogen", "Carbon Dioxide"], "answer": "Hydrogen"},
            {"id": "f96", "question": "What is the symbol for silver?", "options": ["Ag", "Au", "Fe", "Cu"], "answer": "Ag"},
            {"id": "f97", "question": "What is formed when acid and base react?", "options": ["Salt", "Sugar", "Gas", "Metal"], "answer": "Salt"},
            {"id": "f98", "question": "What is the symbol for copper?", "options": ["Cu", "Au", "Ag", "Fe"], "answer": "Cu"},
            {"id": "f99", "question": "What gas is used in fire extinguishers?", "options": ["Carbon Dioxide", "Oxygen", "Nitrogen", "Helium"], "answer": "Carbon Dioxide"},
            {"id": "f100", "question": "What is the pH of pure water?", "options": ["7", "0", "14", "5"], "answer": "7"}
        ],
        "biology": [
            {"id": "f101", "question": "What do plants release during photosynthesis?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Helium"], "answer": "Oxygen"},
            {"id": "f102", "question": "What organ digests food?", "options": ["Stomach", "Heart", "Lungs", "Brain"], "answer": "Stomach"},
            {"id": "f103", "question": "What is the smallest bone in the human body?", "options": ["Stapes", "Femur", "Skull", "Ribs"], "answer": "Stapes"},
            {"id": "f104", "question": "What gas do animals need?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Helium"], "answer": "Oxygen"},
            {"id": "f105", "question": "What part of the plant holds it in the ground?", "options": ["Root", "Leaf", "Stem", "Flower"], "answer": "Root"},
            {"id": "f106", "question": "What is the brain part of?", "options": ["Nervous System", "Digestive System", "Circulatory System", "Respiratory System"], "answer": "Nervous System"},
            {"id": "f107", "question": "What do birds use to fly?", "options": ["Wings", "Legs", "Beak", "Tail"], "answer": "Wings"},
            {"id": "f108", "question": "What is the largest mammal?", "options": ["Blue Whale", "Elephant", "Giraffe", "Lion"], "answer": "Blue Whale"},
            {"id": "f109", "question": "What helps fish swim?", "options": ["Fins", "Gills", "Scales", "Eyes"], "answer": "Fins"},
            {"id": "f110", "question": "What is blood carried by?", "options": ["Veins", "Bones", "Skin", "Muscles"], "answer": "Veins"}
        ],
        "math": [
            {"id": "f111", "question": "What is 7 + 5?", "options": ["12", "11", "13", "10"], "answer": "12"},
            {"id": "f112", "question": "What is 15 - 6?", "options": ["9", "8", "10", "7"], "answer": "9"},
            {"id": "f113", "question": "What is 4 × 5?", "options": ["20", "16", "25", "15"], "answer": "20"},
            {"id": "f114", "question": "What is 18 ÷ 3?", "options": ["6", "5", "7", "4"], "answer": "6"},
            {"id": "f115", "question": "What is 9 + 8?", "options": ["17", "16", "18", "15"], "answer": "17"},
            {"id": "f116", "question": "What is 12 - 4?", "options": ["8", "7", "9", "6"], "answer": "8"},
            {"id": "f117", "question": "What is 6 × 3?", "options": ["18", "15", "12", "20"], "answer": "18"},
            {"id": "f118", "question": "What is 24 ÷ 4?", "options": ["6", "5", "7", "8"], "answer": "6"},
            {"id": "f119", "question": "What is 10 + 7?", "options": ["17", "16", "18", "15"], "answer": "17"},
            {"id": "f120", "question": "What is 14 - 5?", "options": ["9", "8", "10", "7"], "answer": "9"}
        ]
    },
    "Class 9": {
        "physics": [
            {"id": "f9p1", "question": "What is the unit of force?", "options": ["Newton", "Joule", "Watt", "Volt"], "answer": "Newton"},
            {"id": "f9p2", "question": "What causes day and night?", "options": ["Earth's rotation", "Sun's movement", "Moon's orbit", "Clouds"], "answer": "Earth's rotation"},
            {"id": "f9p3", "question": "What is the primary source of Earth's energy?", "options": ["Sun", "Moon", "Wind", "Water"], "answer": "Sun"},
            {"id": "f9p4", "question": "What is the boiling point of water?", "options": ["100°C", "0°C", "50°C", "200°C"], "answer": "100°C"},
            {"id": "f9p5", "question": "What is the freezing point of water?", "options": ["0°C", "100°C", "-10°C", "50°C"], "answer": "0°C"},
            {"id": "f9p6", "question": "What is gravity measured in?", "options": ["m/s²", "kg", "m", "J"], "answer": "m/s²"},
            {"id": "f9p7", "question": "What is the SI unit of time?", "options": ["Second", "Minute", "Hour", "Day"], "answer": "Second"},
            {"id": "f9p8", "question": "What is the largest planet?", "options": ["Jupiter", "Earth", "Mars", "Saturn"], "answer": "Jupiter"},
            {"id": "f9p9", "question": "What gas is most abundant in Earth's atmosphere?", "options": ["Nitrogen", "Oxygen", "Carbon Dioxide", "Argon"], "answer": "Nitrogen"},
            {"id": "f9p10", "question": "What is the unit of distance?", "options": ["Meter", "Kilogram", "Second", "Liter"], "answer": "Meter"}
        ],
        "chemistry": [
            {"id": "f9c1", "question": "What is water made of?", "options": ["H₂O", "CO₂", "O₂", "N₂"], "answer": "H₂O"},
            {"id": "f9c2", "question": "What gas do we breathe?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Helium"], "answer": "Oxygen"},
            {"id": "f9c3", "question": "What is table salt’s common name?", "options": ["Sodium Chloride", "Sugar", "Pepper", "Baking Soda"], "answer": "Sodium Chloride"},
            {"id": "f9c4", "question": "What gas helps things burn?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Hydrogen"], "answer": "Oxygen"},
            {"id": "f9c5", "question": "What is rust made from?", "options": ["Iron Oxide", "Copper", "Silver", "Gold"], "answer": "Iron Oxide"},
            {"id": "f9c6", "question": "What turns litmus paper red?", "options": ["Acid", "Base", "Salt", "Water"], "answer": "Acid"},
            {"id": "f9c7", "question": "What is the symbol for hydrogen?", "options": ["H", "O", "C", "N"], "answer": "H"},
            {"id": "f9c8", "question": "What is vinegar an example of?", "options": ["Acid", "Base", "Salt", "Sugar"], "answer": "Acid"},
            {"id": "f9c9", "question": "What gas is produced by burning?", "options": ["Carbon Dioxide", "Oxygen", "Nitrogen", "Helium"], "answer": "Carbon Dioxide"},
            {"id": "f9c10", "question": "What is the symbol for carbon?", "options": ["C", "H", "O", "N"], "answer": "C"}
        ],
        "biology": [
            {"id": "f9b1", "question": "What do plants need to make food?", "options": ["Sunlight", "Darkness", "Sound", "Heat"], "answer": "Sunlight"},
            {"id": "f9b2", "question": "What is the largest organ in the human body?", "options": ["Skin", "Heart", "Brain", "Lungs"], "answer": "Skin"},
            {"id": "f9b3", "question": "What gas do plants use?", "options": ["Carbon Dioxide", "Oxygen", "Nitrogen", "Helium"], "answer": "Carbon Dioxide"},
            {"id": "f9b4", "question": "What carries oxygen in blood?", "options": ["Red Blood Cells", "White Blood Cells", "Platelets", "Plasma"], "answer": "Red Blood Cells"},
            {"id": "f9b5", "question": "What is the process of making food in plants?", "options": ["Photosynthesis", "Respiration", "Digestion", "Circulation"], "answer": "Photosynthesis"},
            {"id": "f9b6", "question": "What is the human body’s control center?", "options": ["Brain", "Heart", "Lungs", "Stomach"], "answer": "Brain"},
            {"id": "f9b7", "question": "What do animals breathe out?", "options": ["Carbon Dioxide", "Oxygen", "Nitrogen", "Helium"], "answer": "Carbon Dioxide"},
            {"id": "f9b8", "question": "What is the basic unit of life?", "options": ["Cell", "Atom", "Molecule", "Tissue"], "answer": "Cell"},
            {"id": "f9b9", "question": "What pumps blood in the body?", "options": ["Heart", "Lungs", "Brain", "Liver"], "answer": "Heart"},
            {"id": "f9b10", "question": "What do leaves use to make food?", "options": ["Chlorophyll", "Sugar", "Water", "Soil"], "answer": "Chlorophyll"}
        ],
        "math": [
            {"id": "f9m1", "question": "What is 5 + 7?", "options": ["10", "11", "12", "13"], "answer": "12"},
            {"id": "f9m2", "question": "What is the area of a square with side 4?", "options": ["12", "16", "20", "8"], "answer": "16"},
            {"id": "f9m3", "question": "What is 10 - 3?", "options": ["7", "6", "8", "9"], "answer": "7"},
            {"id": "f9m4", "question": "What is 6 × 2?", "options": ["10", "12", "14", "8"], "answer": "12"},
            {"id": "f9m5", "question": "What is 15 ÷ 3?", "options": ["5", "4", "6", "3"], "answer": "5"},
            {"id": "f9m6", "question": "What is the perimeter of a square with side 5?", "options": ["20", "15", "25", "10"], "answer": "20"},
            {"id": "f9m7", "question": "What is 8 + 9?", "options": ["17", "16", "18", "15"], "answer": "17"},
            {"id": "f9m8", "question": "What is 4²?", "options": ["16", "12", "8", "20"], "answer": "16"},
            {"id": "f9m9", "question": "What is 20 - 7?", "options": ["13", "12", "14", "11"], "answer": "13"},
            {"id": "f9m10", "question": "What is 3 × 5?", "options": ["15", "12", "18", "10"], "answer": "15"}
        ]
    },
    "Class 10": {
        "physics": [
            {"id": "f10p1", "question": "What is the speed of light?", "options": ["300 m/s", "3,000 m/s", "300,000 km/s", "30 km/s"], "answer": "300,000 km/s"},
            {"id": "f10p2", "question": "What is Ohm's Law?", "options": ["V = IR", "P = VI", "F = ma", "E = mc²"], "answer": "V = IR"},
            {"id": "f10p3", "question": "What is the unit of power?", "options": ["Watt", "Joule", "Newton", "Volt"], "answer": "Watt"},
            {"id": "f10p4", "question": "What is the formula for kinetic energy?", "options": ["½mv²", "mv", "mgh", "V = IR"], "answer": "½mv²"},
            {"id": "f10p5", "question": "What is the acceleration due to gravity?", "options": ["9.8 m/s²", "10 m/s²", "8 m/s²", "12 m/s²"], "answer": "9.8 m/s²"},
            {"id": "f10p6", "question": "What is the unit of electric current?", "options": ["Ampere", "Volt", "Ohm", "Watt"], "answer": "Ampere"},
            {"id": "f10p7", "question": "What is the formula for work?", "options": ["F × d", "m × v", "½mv²", "V × I"], "answer": "F × d"},
            {"id": "f10p8", "question": "What is the SI unit of pressure?", "options": ["Pascal", "Newton", "Joule", "Watt"], "answer": "Pascal"},
            {"id": "f10p9", "question": "What is the unit of resistance?", "options": ["Ohm", "Volt", "Ampere", "Watt"], "answer": "Ohm"},
            {"id": "f10p10", "question": "What is the formula for potential energy?", "options": ["mgh", "½mv²", "F × d", "V = IR"], "answer": "mgh"}
        ],
        "chemistry": [
            {"id": "f10c1", "question": "What is the symbol for gold?", "options": ["Au", "Ag", "Fe", "Cu"], "answer": "Au"},
            {"id": "f10c2", "question": "What gas is in soda?", "options": ["Carbon Dioxide", "Oxygen", "Nitrogen", "Helium"], "answer": "Carbon Dioxide"},
            {"id": "f10c3", "question": "What is the symbol for iron?", "options": ["Fe", "Au", "Ag", "Cu"], "answer": "Fe"},
            {"id": "f10c4", "question": "What is a mixture of metals called?", "options": ["Alloy", "Compound", "Element", "Solution"], "answer": "Alloy"},
            {"id": "f10c5", "question": "What gas is flammable?", "options": ["Hydrogen", "Oxygen", "Nitrogen", "Carbon Dioxide"], "answer": "Hydrogen"},
            {"id": "f10c6", "question": "What is the symbol for silver?", "options": ["Ag", "Au", "Fe", "Cu"], "answer": "Ag"},
            {"id": "f10c7", "question": "What is formed when acid and base react?", "options": ["Salt", "Sugar", "Gas", "Metal"], "answer": "Salt"},
            {"id": "f10c8", "question": "What is the symbol for copper?", "options": ["Cu", "Au", "Ag", "Fe"], "answer": "Cu"},
            {"id": "f10c9", "question": "What gas is used in fire extinguishers?", "options": ["Carbon Dioxide", "Oxygen", "Nitrogen", "Helium"], "answer": "Carbon Dioxide"},
            {"id": "f10c10", "question": "What is the pH of pure water?", "options": ["7", "0", "14", "5"], "answer": "7"}
        ],
        "biology": [
            {"id": "f10b1", "question": "What do plants release during photosynthesis?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Helium"], "answer": "Oxygen"},
            {"id": "f10b2", "question": "What organ digests food?", "options": ["Stomach", "Heart", "Lungs", "Brain"], "answer": "Stomach"},
            {"id": "f10b3", "question": "What is the smallest bone in the human body?", "options": ["Stapes", "Femur", "Skull", "Ribs"], "answer": "Stapes"},
            {"id": "f10b4", "question": "What gas do animals need?", "options": ["Oxygen", "Carbon Dioxide", "Nitrogen", "Helium"], "answer": "Oxygen"},
            {"id": "f10b5", "question": "What part of the plant holds it in the ground?", "options": ["Root", "Leaf", "Stem", "Flower"], "answer": "Root"},
            {"id": "f10b6", "question": "What is the brain part of?", "options": ["Nervous System", "Digestive System", "Circulatory System", "Respiratory System"], "answer": "Nervous System"},
            {"id": "f10b7", "question": "What do birds use to fly?", "options": ["Wings", "Legs", "Beak", "Tail"], "answer": "Wings"},
            {"id": "f10b8", "question": "What is the largest mammal?", "options": ["Blue Whale", "Elephant", "Giraffe", "Lion"], "answer": "Blue Whale"},
            {"id": "f10b9", "question": "What helps fish swim?", "options": ["Fins", "Gills", "Scales", "Eyes"], "answer": "Fins"},
            {"id": "f10b10", "question": "What is blood carried by?", "options": ["Veins", "Bones", "Skin", "Muscles"], "answer": "Veins"}
        ],
        "math": [
            {"id": "f10m1", "question": "What is the derivative of x²?", "options": ["x", "2x", "x²", "2"], "answer": "2x"},
            {"id": "f10m2", "question": "Solve: 2x + 3 = 7", "options": ["x = 1", "x = 2", "x = 3", "x = 4"], "answer": "x = 2"},
            {"id": "f10m3", "question": "What is the integral of 2x?", "options": ["x²", "2x²", "x", "4x"], "answer": "x²"},
            {"id": "f10m4", "question": "What is the value of π (approx)?", "options": ["3.14", "3.12", "3.16", "3.10"], "answer": "3.14"},
            {"id": "f10m5", "question": "Solve: x² - 4 = 0", "options": ["x = 2", "x = 3", "x = 1", "x = 0"], "answer": "x = 2"},
            {"id": "f10m6", "question": "What is sin(90°)?", "options": ["1", "0", "0.5", "-1"], "answer": "1"},
            {"id": "f10m7", "question": "What is the slope of y = 3x + 2?", "options": ["3", "2", "1", "0"], "answer": "3"},
            {"id": "f10m8", "question": "What is 5²?", "options": ["25", "20", "15", "30"], "answer": "25"},
            {"id": "f10m9", "question": "What is cos(0°)?", "options": ["1", "0", "0.5", "-1"], "answer": "1"},
            {"id": "f10m10", "question": "Solve: 3x = 12", "options": ["x = 4", "x = 3", "x = 5", "x = 2"], "answer": "x = 4"}
        ]
    }
}

def fetch_quizapi_questions(class_level, subject, username, num_questions=10):
    difficulty = CLASS_DIFFICULTY_MAP.get(class_level, "Easy")
    category = SUBJECT_CATEGORY_MAP.get(subject, "science")
    url = f"https://quizapi.io/api/v1/questions?apiKey={QUIZAPI_KEY}&limit=20&category={category}&difficulty={difficulty}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        questions = []
        for i, q in enumerate(data):
            options = [ans for ans in q["answers"].values() if ans is not None]
            correct_answer = None
            for key, value in q["correct_answers"].items():
                if value == "true":
                    correct_answer = q["answers"][key.replace("_correct", "")]
                    break
            if not options or not correct_answer:
                logger.warning(f"Skipping malformed question: {q}")
                continue
            q_id = q.get("id", f"api_{i + 1}")
            questions.append({
                "id": q_id,
                "question": q["question"],
                "options": options,
                "answer": correct_answer
            })
        
        # Filter out used questions
        room = f"{class_level}_{subject}"
        if username not in used_questions:
            used_questions[username] = {}
        if room not in used_questions[username]:
            used_questions[username][room] = set()
        used_ids = used_questions[username][room]
        available_questions = [q for q in questions if q["id"] not in used_ids]
        
        # Select up to 10 questions
        if len(available_questions) < num_questions:
            logger.warning(f"Not enough new questions for {username} in {room}, using fallback")
            fallback = FALLBACK_QUESTIONS.get(class_level, {}).get(subject, [])
            available_fallback = [q for q in fallback if q["id"] not in used_ids]
            available_questions.extend(available_fallback)
        selected_questions = random.sample(available_questions, min(num_questions, len(available_questions))) if available_questions else []
        
        # Update used questions
        for q in selected_questions:
            used_ids.add(q["id"])
        
        # Shuffle options
        for q in selected_questions:
            random.shuffle(q["options"])
        
        if not selected_questions:
            logger.warning(f"No valid questions for {class_level}/{subject}/{username}")
            fallback = FALLBACK_QUESTIONS.get(class_level, {}).get(subject, [])
            selected_questions = random.sample(fallback, min(num_questions, len(fallback))) if len(fallback) >= num_questions else fallback
        
        logger.debug(f"Fetched questions for {username}: {selected_questions}")
        return selected_questions
    except requests.RequestException as e:
        logger.error(f"Error fetching from QuizAPI.io: {str(e)}")
        fallback = FALLBACK_QUESTIONS.get(class_level, {}).get(subject, [])
        available_fallback = [q for q in fallback if q["id"] not in used_questions.get(username, {}).get(f"{class_level}_{subject}", set())]
        return random.sample(available_fallback, min(num_questions, len(available_fallback))) if len(available_fallback) >= num_questions else available_fallback

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/lab-advisor')
def lab_advisor_page():
    return render_template('lab_advisor.html')

@app.route('/chatbot')
def chatbot_page():
    return render_template('chatbot.html')

@app.route('/collab')
def collab_page():
    return render_template('collab.html')

@app.route('/quiz')
def quiz_page():
    return render_template('quiz.html')

@app.route('/collab/<subject>')
def collab_subject_page(subject):
    return render_template('collab.html', subject=subject)

@app.route('/code-editor')
def code_editor_page():
    return render_template('code.html')

@app.route('/gamified')
def gamified_page():
    return render_template('gamified.html')

@app.route('/api/quiz/questions', methods=['POST'])
def get_quiz_questions():
    data = request.json
    class_level = data.get("class", "")
    subject = data.get("subject", "")
    username = data.get("username", "")
    if not class_level or not subject or not username:
        return jsonify({"error": "Class, subject, and username required"}), 400
    
    questions = fetch_quizapi_questions(class_level, subject, username)
    if not questions:
        logger.warning(f"No questions available for {class_level}/{subject}/{username}")
        return jsonify({"error": "No questions available for this selection"}), 500
    return jsonify({"questions": questions})

@app.route('/api/quiz/submit', methods=['POST'])
def submit_quiz():
    data = request.json
    username = data.get("username", "").strip()
    class_level = data.get("class", "")
    subject = data.get("subject", "")
    answers = data.get("answers", {})
    questions = data.get("questions", [])
    if not username or not class_level or not subject or not answers or not questions:
        return jsonify({"error": "Username, class, subject, answers, and questions required"}), 400
    
    score = 0
    total = len(questions)
    for q in questions:
        q_id = str(q["id"])
        if q_id in answers and answers[q_id] == q["answer"]:
            score += 10
            logger.debug(f"Correct answer for Q{q_id}: {answers[q_id]}")
        else:
            logger.debug(f"Incorrect answer for Q{q_id}: {answers.get(q_id, 'None')} vs {q['answer']}")
    room = f"{class_level}_{subject}"
    if room not in leaderboard:
        leaderboard[room] = {}
    leaderboard[room][username] = {
        "score": leaderboard[room].get(username, {}).get("score", 0) + score,
        "last_updated": datetime.now().isoformat()
    }
    logger.debug(f"Quiz submitted for {username} in {room}: Score {score}/{total * 10}")
    socketio.emit("leaderboard_updated", {"leaderboard": leaderboard[room], "room": room}, room=room)
    return jsonify({"score": score, "total": total * 10})

@app.route('/api/quiz/leaderboard', methods=['POST'])
def get_quiz_leaderboard():
    data = request.json
    class_level = data.get("class", "")
    subject = data.get("subject", "")
    if not class_level or not subject:
        return jsonify({"error": "Class and subject required"}), 400
    room = f"{class_level}_{subject}"
    lb = leaderboard.get(room, {})
    logger.debug(f"Fetching leaderboard for {room}: {lb}")
    return jsonify({"leaderboard": lb})

@app.route('/api/gamified/questions', methods=['POST'])
def get_gamified_questions():
    data = request.json
    class_level = data.get("class", "")
    subject = data.get("subject", "")
    username = data.get("username", "")
    if not class_level or not subject or not username:
        return jsonify({"error": "Class, subject, and username required"}), 400
    
    questions = fetch_quizapi_questions(class_level, subject, username)
    if not questions:
        logger.warning(f"No questions available for {class_level}/{subject}/{username}")
        return jsonify({"error": "No questions available for this selection"}), 500
    return jsonify({"questions": questions})

@app.route('/api/gamified/submit', methods=['POST'])
def submit_gamified_quiz():
    data = request.json
    username = data.get("username", "").strip()
    class_level = data.get("class", "")
    subject = data.get("subject", "")
    answers = data.get("answers", {})
    questions = data.get("questions", [])
    if not username or not class_level or not subject or not answers or not questions:
        return jsonify({"error": "Username, class, subject, answers, and questions required"}), 400
    
    score = 0
    total = len(questions)
    for q in questions:
        q_id = str(q["id"])
        if q_id in answers and answers[q_id] == q["answer"]:
            score += 10
            logger.debug(f"Correct answer for Q{q_id}: {answers[q_id]}")
        else:
            logger.debug(f"Incorrect answer for Q{q_id}: {answers.get(q_id, 'None')} vs {q['answer']}")
    room = f"{class_level}_{subject}"
    if room not in leaderboard:
        leaderboard[room] = {}
    leaderboard[room][username] = {
        "score": leaderboard[room].get(username, {}).get("score", 0) + score,
        "last_updated": datetime.now().isoformat()
    }
    logger.debug(f"Quiz submitted for {username} in {room}: Score {score}/{total * 10}")
    socketio.emit("leaderboard_updated", {"leaderboard": leaderboard[room], "room": room}, room=room)
    return jsonify({"score": score, "total": total * 10})

@app.route('/api/gamified/leaderboard', methods=['POST'])
def get_gamified_leaderboard():
    data = request.json
    class_level = data.get("class", "")
    subject = data.get("subject", "")
    if not class_level or not subject:
        return jsonify({"error": "Class and subject required"}), 400
    room = f"{class_level}_{subject}"
    lb = leaderboard.get(room, {})
    logger.debug(f"Fetching leaderboard for {room}: {lb}")
    return jsonify({"leaderboard": lb})

@app.route('/api/lab_advisor', methods=['POST'])
def lab_advisor():
    try:
        experiment_topic = request.json.get("topic", "")
        target_language = request.json.get("language", "en")
        if not experiment_topic:
            return jsonify({"reply": "⚠️ Please enter an experiment topic."}), 400
        prompt = f"Provide guidance on the {experiment_topic} experiment."
        response = ollama.chat(model="gemma:2b", messages=[{"role": "user", "content": prompt}])
        reply = response.get("message", {}).get("content", "Sorry, I couldn't generate a response.")
        translated_reply = GoogleTranslator(source="auto", target=target_language).translate(reply)
        return jsonify({"reply": translated_reply})
    except Exception as e:
        return jsonify({"reply": f"⚠️ Error: {str(e)}"}), 500

@app.route('/api/lab_report', methods=['POST'])
def generate_lab_report():
    try:
        experiment_data = request.json.get("experiment_data", "")
        target_language = request.json.get("language", "en")
        if not experiment_data:
            return jsonify({"report": "⚠️ Please enter experiment details."}), 400
        prompt = f"Generate a structured lab report for: {experiment_data}"
        response = ollama.chat(model="gemma:2b", messages=[{"role": "user", "content": prompt}])
        report_content = response.get("message", {}).get("content", "Sorry, I couldn't generate the lab report.")
        translated_report = GoogleTranslator(source="auto", target=target_language).translate(report_content)
        return jsonify({"report": translated_report})
    except Exception as e:
        return jsonify({"report": f"⚠️ Error: {str(e)}"}), 500

@app.route('/api/download_lab_report', methods=['POST'])
def download_lab_report():
    try:
        report_content = request.json.get("report", "No report content available.")
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", style="B", size=16)
        pdf.cell(200, 10, "AI Lab Report", ln=True, align="C")
        pdf.set_font("Arial", size=12)
        for line in report_content.split("\n"):
            pdf.multi_cell(0, 10, line)
            pdf.ln(1)
        pdf_filename = "lab_report.pdf"
        pdf.output(pdf_filename)
        return send_file(pdf_filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": f"⚠️ PDF Generation Error: {str(e)}"}), 500

@app.route('/run_code', methods=['POST'])
def run_code():
    try:
        data = request.json
        code = data.get("code", "")
        language = data.get("language", "python").lower()
        if not code:
            return jsonify({"output": "⚠️ No code provided.", "errors": []}), 400

        if language not in SUPPORTED_LANGUAGES:
            return jsonify({"output": f"Unsupported language: {language}. Supported: {', '.join(SUPPORTED_LANGUAGES)}", "errors": []}), 400

        # Mock execution with basic error detection
        commands = {
            "python": ["python3", "-c", code],
            "javascript": ["node", "-e", code],
            "java": ["echo", "Java not fully supported in mock"],
            "cpp": ["echo", "C++ not fully supported in mock"]
        }

        try:
            result = subprocess.run(commands[language], capture_output=True, text=True, timeout=10)
            output = result.stdout if result.returncode == 0 else result.stderr
        except subprocess.TimeoutExpired:
            output = "⚠️ Execution timed out."
        except Exception as e:
            output = f"⚠️ Execution error: {str(e)}"

        # Basic error detection (mocked)
        errors = []
        if language == "python":
            if "print(" in code and not ")" in code:
                errors.append({"line": code.split("\n").index("print(") + 1, "message": "Missing closing parenthesis"})
        elif language == "javascript":
            if "console.log(" in code and not ";" in code:
                errors.append({"line": code.split("\n").index("console.log(") + 1, "message": "Missing semicolon"})
        elif language == "java":
            if "System.out.println(" in code and not ";" in code:
                errors.append({"line": code.split("\n").index("System.out.println(") + 1, "message": "Missing semicolon"})
        elif language == "cpp":
            if "cout" in code and not ";" in code:
                errors.append({"line": code.split("\n").index("cout") + 1, "message": "Missing semicolon"})

        return jsonify({"output": output, "errors": errors})
    except Exception as e:
        logger.error(f"Run code error: {str(e)}")
        return jsonify({"output": f"⚠️ Error: {str(e)}", "errors": []}), 500

@app.route('/api/run_tests', methods=['POST'])
def run_tests():
    try:
        data = request.json
        code = data.get("code", "")
        language = data.get("language", "python").lower()
        if not code:
            return jsonify({"results": "⚠️ No code provided."}), 400

        results = []
        test_cases = TEST_CASES.get(language, {})
        for test_input, expected in test_cases.items():
            if test_input in code:
                try:
                    result = subprocess.run(
                        {"python": ["python3", "-c", code], "javascript": ["node", "-e", code]}[language],
                        capture_output=True, text=True, timeout=5
                    )
                    output = result.stdout if result.returncode == 0 else result.stderr
                    passed = output == expected["expected_output"]
                    results.append({
                        "description": expected["description"],
                        "passed": passed,
                        "output": output,
                        "expected": expected["expected_output"]
                    })
                except Exception as e:
                    results.append({
                        "description": expected["description"],
                        "passed": False,
                        "output": f"Error: {str(e)}",
                        "expected": expected["expected_output"]
                    })
            else:
                results.append({
                    "description": expected["description"],
                    "passed": False,
                    "output": "Code pattern not found.",
                    "expected": expected["expected_output"]
                })

        return jsonify({"results": results})
    except Exception as e:
        logger.error(f"Run tests error: {str(e)}")
        return jsonify({"results": f"⚠️ Error: {str(e)}"}), 500

@app.route('/api/match_peers', methods=['POST'])
def match_peers():
    topic = request.json.get("topic", "").lower()
    subject = request.json.get("subject", "").lower()
    user_id = request.json.get("user_id", "Anonymous")
    if not topic or not subject:
        return jsonify({"peers": [], "message": "⚠️ Enter a topic and subject."})
    peers_in_subject = active_rooms.get(subject, [])
    available_peers = [p for p in peers_in_subject if p != user_id]
    if not available_peers:
        return jsonify({"peers": [], "message": "No peers online yet—invite friends!"})
    return jsonify({"peers": available_peers, "message": f"Found {len(available_peers)} peer(s) for {topic}"})

# SocketIO Events for Collaboration and WebRTC
@socketio.on("join_room")
def handle_join_room(data):
    room = data["room"]
    user_id = data.get("user_id", "Anonymous")
    join_room(room)
    if room not in active_rooms:
        active_rooms[room] = []
    if user_id not in active_rooms[room]:
        active_rooms[room].append(user_id)
    emit("message", {"text": f"{user_id} joined the {room} room!", "type": "system"}, room=room)
    emit("user_count", {"count": len(active_rooms[room])}, room=room)
    emit("user_list", {"users": active_rooms[room]}, room=room)

@socketio.on("group_message")
def handle_group_message(data):
    room = data["room"]
    text = data["text"]
    user_id = data.get("user_id", "Anonymous")
    if text.startswith("@"):
        try:
            target_user = text.split(" ")[0][1:]
            if target_user in active_rooms.get(room, []):
                message = text[len(target_user) + 2:]
                emit("message", {"text": f"{user_id} to {target_user}: {message}", "type": "private", "from": user_id, "to": target_user}, room=room)
                logger.debug(f"Private message from {user_id} to {target_user}: {message}")
            else:
                emit("message", {"text": f"{user_id}: User {target_user} not found.", "type": "system"}, to=user_id)
            return
        except:
            emit("message", {"text": f"{user_id}: Invalid private message format. Use @username message", "type": "system"}, to=user_id)
            return
    
    emit("message", {"text": f"{user_id}: {text}", "type": "student"}, room=room)
    try:
        response = ollama.chat(model="gemma:2b", messages=[{"role": "user", "content": f"Facilitate this group discussion on {room}: {text}"}])
        reply = response.get("message", {}).get("content", "Let’s discuss this!")
        emit("message", {"text": f"AI: {reply}", "type": "ai"}, room=room)
    except Exception as e:
        logger.error(f"AI response error: {str(e)}")
        emit("message", {"text": "AI: I’m having trouble—keep the discussion going!", "type": "ai"}, room=room)

@socketio.on("invite_peer")
def handle_invite_peer(data):
    room = data["room"]
    peer_id = data["peer_id"]
    user_id = data["user_id"]
    emit("message", {"text": f"{user_id} invited {peer_id} to discuss {data['topic']}", "type": "system"}, room=room)
    emit("message", {"text": f"{user_id} to {peer_id}: Let’s discuss {data['topic']}!", "type": "private", "from": user_id, "to": peer_id}, room=room)

@socketio.on("update_code")
def handle_update_code(data):
    room = data["room"]
    user_id = data["user_id"]
    code = data["code"]
    emit("code_updated", {"code": code, "user_id": user_id}, room=room, broadcast=True)

@socketio.on("update_cursor")
def handle_update_cursor(data):
    room = data["room"]
    user_id = data["user_id"]
    position = data["position"]
    if room not in cursor_positions:
        cursor_positions[room] = {}
    cursor_positions[room][user_id] = {"position": position}
    emit("cursor_update", cursor_positions[room], room=room, broadcast=True)

@socketio.on("run_code")
def handle_run_code(data):
    room = data["room"]
    code = data["code"]
    language = data["language"]
    user_id = data["user_id"]
    try:
        result = subprocess.run(
            {"python": ["python3", "-c", code], "javascript": ["node", "-e", code]}[language.lower()],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout if result.returncode == 0 else f"⚠️ Error: {result.stderr}"
        emit("run_result", {"text": f"{user_id} ran code:\nOutput: {output}", "user_id": user_id}, room=room)
    except Exception as e:
        logger.error(f"Run code error: {str(e)}")
        emit("run_result", {"text": f"{user_id} ran code:\nOutput: ⚠️ Error: {str(e)}", "user_id": user_id}, room=room)

@socketio.on("draw")
def handle_draw(data):
    room = data["room"]
    emit("draw", data, room=room, broadcast=True)

@socketio.on("clear_board")
def handle_clear_board(data):
    room = data["room"]
    emit("clear_board", {}, room=room, broadcast=True)

# WebRTC Signaling for Code Editor Collaboration
@socketio.on("offer")
def handle_offer(data):
    room = data["room"]
    offer = data["offer"]
    user_id = data["user_id"]
    emit("offer", {"room": room, "offer": offer, "user_id": user_id}, room=room, broadcast=True)

@socketio.on("answer")
def handle_answer(data):
    room = data["room"]
    answer = data["answer"]
    user_id = data["user_id"]
    emit("answer", {"room": room, "answer": answer, "user_id": user_id}, room=room, broadcast=True)

@socketio.on("ice-candidate")
def handle_ice_candidate(data):
    room = data["room"]
    candidate = data["candidate"]
    user_id = data["user_id"]
    emit("ice-candidate", {"room": room, "candidate": candidate, "user_id": user_id}, room=room, broadcast=True)

@socketio.on("webrtc-data")
def handle_webrtc_data(data):
    room = data["room"]
    user_id = data["user_id"]
    data_type = data["type"]
    payload = data["payload"]
    emit("webrtc-data", {"type": data_type, "payload": payload, "user_id": user_id}, room=room, broadcast=True)

if __name__ == "__main__":
    socketio.run(app, debug=True)

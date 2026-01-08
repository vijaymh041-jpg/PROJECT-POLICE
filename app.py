from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta, timezone
import json
import bcrypt
from pymongo import MongoClient
from bson import ObjectId
import os
import urllib.parse
import csv
import io
import requests
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import re

app = Flask(__name__)
app.config.from_object('config.Config')

# --- CONFIGURATION & TIMEZONE ---
IST = timezone(timedelta(hours=5, minutes=30))

# --- AUTHENTIC POLICE DATABASE ---
POLICE_DATABASE = {
    # --- USER SPECIFIC REQUESTS ---
    "KTJ Nagara-2 Police Station": {"ward": "26", "reg_no": "170026"},
    "KTJ Nagara-1 Police Station": {"ward": "27", "reg_no": "170027"},

    # --- BENGALURU CITY (Code 01) ---
    "Ashok Nagar Police Station": {"ward": "111", "reg_no": "010111"},
    "Basavanagudi Police Station": {"ward": "154", "reg_no": "010154"},
    "Chamarajpet Police Station": {"ward": "139", "reg_no": "010139"},
    "Commercial Street Police Station": {"ward": "110", "reg_no": "010110"},
    "Cubbon Park Police Station": {"ward": "109", "reg_no": "010109"},
    "Halasuru Police Station": {"ward": "112", "reg_no": "010112"},
    "High Grounds Police Station": {"ward": "093", "reg_no": "010093"},
    "Jayanagar Police Station": {"ward": "169", "reg_no": "010169"},
    "K.G. Halli Police Station": {"ward": "030", "reg_no": "010030"},
    "K.R. Market Police Station": {"ward": "138", "reg_no": "010138"},
    "Koramangala Police Station": {"ward": "151", "reg_no": "010151"},
    "Madiwala Police Station": {"ward": "172", "reg_no": "010172"},
    "Mahalakshmi Layout Police Station": {"ward": "068", "reg_no": "010068"},
    "Malleshwaram Police Station": {"ward": "045", "reg_no": "010045"},
    "Seshadripuram Police Station": {"ward": "094", "reg_no": "010094"},
    "Shivajinagar Police Station": {"ward": "108", "reg_no": "010108"},
    "Ulsoor Police Station": {"ward": "089", "reg_no": "010089"},
    "Vijayanagar Police Station": {"ward": "123", "reg_no": "010123"},
    "Whitefield Police Station": {"ward": "084", "reg_no": "010084"},
    "Yelahanka Police Station": {"ward": "004", "reg_no": "010004"},

    # --- DAVANAGERE DISTRICT (Code 17) ---
    "Davanagere Traffic Police Station": {"ward": "001", "reg_no": "170001"},
    "Davanagere Women Police Station": {"ward": "002", "reg_no": "170002"},
    "Jagalur Police Station": {"ward": "012", "reg_no": "170012"},
    "Channagiri Police Station": {"ward": "014", "reg_no": "170014"},
    "Harapanahalli Police Station": {"ward": "018", "reg_no": "170018"},
    "Harihar Police Station": {"ward": "020", "reg_no": "170020"},
    "Honnali Police Station": {"ward": "022", "reg_no": "170022"},
    "Nyamathi Police Station": {"ward": "024", "reg_no": "170024"},
    "Davanagere Extension Police Station": {"ward": "010", "reg_no": "170010"},
    "Davanagere Rural Police Station": {"ward": "015", "reg_no": "170015"},

    # --- MYSURU CITY (Code 09) ---
    "Vijayanagar Police Station Mysuru": {"ward": "031", "reg_no": "090031"},
    "Nazarabad Police Station": {"ward": "030", "reg_no": "090030"},
    "K.R. Police Station Mysuru": {"ward": "035", "reg_no": "090035"},
    "Metagalli Police Station": {"ward": "018", "reg_no": "090018"},
    "Lashkar Police Station": {"ward": "022", "reg_no": "090022"},
    "Jayanagar Police Station Mysuru": {"ward": "040", "reg_no": "090040"},
    "Saraswathipuram Police Station": {"ward": "042", "reg_no": "090042"},
    "Kuvempunagar Police Station": {"ward": "045", "reg_no": "090045"},
    "Ashokapuram Police Station": {"ward": "048", "reg_no": "090048"},

    # --- HUBBALLI-DHARWAD (Code 25) ---
    "Hubballi Traffic Police Station": {"ward": "050", "reg_no": "250050"},
    "Old Hubballi Police Station": {"ward": "055", "reg_no": "250055"},
    "Vidyanagar Police Station": {"ward": "060", "reg_no": "250060"},
    "Dharwad Police Station": {"ward": "010", "reg_no": "250010"},
    "Keshavpur Police Station": {"ward": "062", "reg_no": "250062"},
    "Navanagar Police Station": {"ward": "045", "reg_no": "250045"},
    "Suburban Police Station Hubballi": {"ward": "052", "reg_no": "250052"},
    "Dharwad Town Police Station": {"ward": "012", "reg_no": "250012"},

    # --- MANGALURU CITY (Code 19) ---
    "Mangaluru North Police Station": {"ward": "020", "reg_no": "190020"},
    "Mangaluru South Police Station": {"ward": "021", "reg_no": "190021"},
    "Kadri Police Station": {"ward": "022", "reg_no": "190022"},
    "Bunder Police Station": {"ward": "025", "reg_no": "190025"},
    "Pandeshwar Police Station": {"ward": "028", "reg_no": "190028"},
    "Urwa Police Station": {"ward": "018", "reg_no": "190018"},
    "Barke Police Station": {"ward": "019", "reg_no": "190019"},
    "Kankanady Police Station": {"ward": "030", "reg_no": "190030"},

    # --- BELAGAVI (Code 22) ---
    "Belagavi Traffic Police Station": {"ward": "005", "reg_no": "220005"},
    "Khanapur Police Station": {"ward": "050", "reg_no": "220050"},
    "Gokul Road Police Station": {"ward": "015", "reg_no": "220015"},
    "Sadashiv Nagar Police Station": {"ward": "020", "reg_no": "220020"},
    "Camp Police Station Belagavi": {"ward": "008", "reg_no": "220008"},
    "Khade Bazar Police Station": {"ward": "010", "reg_no": "220010"},
    "Market Police Station Belagavi": {"ward": "012", "reg_no": "220012"},
    "APMC Police Station Belagavi": {"ward": "025", "reg_no": "220025"},

    # --- KALABURAGI (Code 32) ---
    "Kalaburagi Traffic Police Station": {"ward": "005", "reg_no": "320005"},
    "Jewargi Police Station": {"ward": "040", "reg_no": "320040"},
    "Sedam Police Station": {"ward": "045", "reg_no": "320045"},
    "Station Bazar Police Station": {"ward": "010", "reg_no": "320010"},
    "Ashok Nagar Police Station Kalaburagi": {"ward": "015", "reg_no": "320015"},
    "Brahmapur Police Station": {"ward": "020", "reg_no": "320020"},

    # --- TUMAKURU (Code 06) ---
    "Tumakuru Town Police Station": {"ward": "001", "reg_no": "060001"},
    "Tumakuru Rural Police Station": {"ward": "005", "reg_no": "060005"},
    "New Extension Police Station Tumakuru": {"ward": "003", "reg_no": "060003"},
    "Tilak Park Police Station": {"ward": "002", "reg_no": "060002"},
    "Kyathasandra Police Station": {"ward": "006", "reg_no": "060006"},
    "Gubbi Police Station": {"ward": "020", "reg_no": "060020"},
    "Kunigal Police Station": {"ward": "030", "reg_no": "060030"},
    "Sira Town Police Station": {"ward": "040", "reg_no": "060040"},
    "Tiptur Town Police Station": {"ward": "050", "reg_no": "060050"},
    "Madhugiri Police Station": {"ward": "060", "reg_no": "060060"},
    "Pavagada Police Station": {"ward": "070", "reg_no": "060070"},
    "Chikkanayakanahalli Police Station": {"ward": "080", "reg_no": "060080"},
    "Koratagere Police Station": {"ward": "090", "reg_no": "060090"},
    "Turuvekere Police Station": {"ward": "095", "reg_no": "060095"},
    "Hebburu Police Station": {"ward": "098", "reg_no": "060098"},

    # --- SHIVAMOGGA (Code 14) ---
    "Shivamogga Doddapete Police Station": {"ward": "001", "reg_no": "140001"},
    "Shivamogga Kote Police Station": {"ward": "002", "reg_no": "140002"},
    "Tunganagar Police Station": {"ward": "005", "reg_no": "140005"},
    "Vinobhanagar Police Station": {"ward": "004", "reg_no": "140004"},
    "Shivamogga Rural Police Station": {"ward": "010", "reg_no": "140010"},
    "Bhadravathi Old Town Police Station": {"ward": "020", "reg_no": "140020"},
    "Bhadravathi New Town Police Station": {"ward": "021", "reg_no": "140021"},
    "Paper Town Police Station": {"ward": "022", "reg_no": "140022"},
    "Sagar Town Police Station": {"ward": "030", "reg_no": "140030"},
    "Sagar Rural Police Station": {"ward": "031", "reg_no": "140031"},
    "Shikaripura Police Station": {"ward": "040", "reg_no": "140040"},
    "Soraba Police Station": {"ward": "050", "reg_no": "140050"},
    "Thirthahalli Police Station": {"ward": "060", "reg_no": "140060"},
    "Hosanagara Police Station": {"ward": "070", "reg_no": "140070"},

    # --- BALLARI (Code 34) ---
    "Ballari Brucepet Police Station": {"ward": "001", "reg_no": "340001"},
    "Ballari Cowl Bazar Police Station": {"ward": "002", "reg_no": "340002"},
    "Ballari Gandhinagar Police Station": {"ward": "003", "reg_no": "340003"},
    "Ballari Rural Police Station": {"ward": "005", "reg_no": "340005"},
    "APMC Yard Police Station Ballari": {"ward": "008", "reg_no": "340008"},
    "Kurugodu Police Station": {"ward": "015", "reg_no": "340015"},
    "Siruguppa Police Station": {"ward": "020", "reg_no": "340020"},
    "Sandur Police Station": {"ward": "030", "reg_no": "340030"},
    "Kudligi Police Station": {"ward": "040", "reg_no": "340040"},
    "Hospet Town Police Station": {"ward": "050", "reg_no": "340050"},
    "Hospet Rural Police Station": {"ward": "051", "reg_no": "340051"},
    "Hagaribommanahalli Police Station": {"ward": "060", "reg_no": "340060"},
    "Kampli Police Station": {"ward": "065", "reg_no": "340065"},
    "Toranagallu Police Station": {"ward": "070", "reg_no": "340070"},

    # --- VIJAYAPURA (Code 28) ---
    "Vijayapura Gandhi Chowk Police Station": {"ward": "001", "reg_no": "280001"},
    "Vijayapura Gol Gumbaz Police Station": {"ward": "002", "reg_no": "280002"},
    "Vijayapura Jalnagar Police Station": {"ward": "003", "reg_no": "280003"},
    "Vijayapura APMC Police Station": {"ward": "004", "reg_no": "280004"},
    "Vijayapura Rural Police Station": {"ward": "005", "reg_no": "280005"},
    "Indi Police Station": {"ward": "020", "reg_no": "280020"},
    "Sindagi Police Station": {"ward": "030", "reg_no": "280030"},
    "Basavana Bagewadi Police Station": {"ward": "040", "reg_no": "280040"},
    "Muddebihal Police Station": {"ward": "050", "reg_no": "280050"},
    "Talikoti Police Station": {"ward": "055", "reg_no": "280055"},
    "Tikota Police Station": {"ward": "060", "reg_no": "280060"},

    # --- HASSAN (Code 13) ---
    "Hassan Town Police Station": {"ward": "001", "reg_no": "130001"},
    "Hassan Extension Police Station": {"ward": "002", "reg_no": "130002"},
    "Hassan Rural Police Station": {"ward": "005", "reg_no": "130005"},
    "Arsikere Town Police Station": {"ward": "010", "reg_no": "130010"},
    "Arsikere Rural Police Station": {"ward": "011", "reg_no": "130011"},
    "Channarayapatna Town Police Station": {"ward": "020", "reg_no": "130020"},
    "Sakleshpur Town Police Station": {"ward": "030", "reg_no": "130030"},
    "Belur Police Station": {"ward": "040", "reg_no": "130040"},
    "Holenarasipura Police Station": {"ward": "050", "reg_no": "130050"},
    "Arkalgud Police Station": {"ward": "060", "reg_no": "130060"},
    "Alur Police Station": {"ward": "070", "reg_no": "130070"},
    "Yeslur Police Station": {"ward": "075", "reg_no": "130075"},
    "Nuggehalli Police Station": {"ward": "080", "reg_no": "130080"},

    # --- UDUPI (Code 20) ---
    "Udupi Town Police Station": {"ward": "001", "reg_no": "200001"},
    "Malpe Police Station": {"ward": "005", "reg_no": "200005"},
    "Manipal Police Station": {"ward": "006", "reg_no": "200006"},
    "Brahmavara Police Station": {"ward": "010", "reg_no": "200010"},
    "Kundapura Police Station": {"ward": "020", "reg_no": "200020"},
    "Byndoor Police Station": {"ward": "030", "reg_no": "200030"},
    "Karkala Town Police Station": {"ward": "040", "reg_no": "200040"},
    "Karkala Rural Police Station": {"ward": "041", "reg_no": "200041"},
    "Kaup Police Station": {"ward": "050", "reg_no": "200050"},
    "Padubidri Police Station": {"ward": "055", "reg_no": "200055"},
    "Kollur Police Station": {"ward": "060", "reg_no": "200060"},
    "Kota Police Station": {"ward": "065", "reg_no": "200065"},
    "Shankaranarayana Police Station": {"ward": "070", "reg_no": "200070"},

    # --- MANDYA (Code 11) ---
    "Mandya West Police Station": {"ward": "001", "reg_no": "110001"},
    "Mandya East Police Station": {"ward": "002", "reg_no": "110002"},
    "Mandya Rural Police Station": {"ward": "005", "reg_no": "110005"},
    "Maddur Police Station": {"ward": "010", "reg_no": "110010"},
    "Malavalli Town Police Station": {"ward": "020", "reg_no": "110020"},
    "Malavalli Rural Police Station": {"ward": "021", "reg_no": "110021"},
    "Srirangapatna Police Station": {"ward": "030", "reg_no": "110030"},
    "K.R. Pet Town Police Station": {"ward": "040", "reg_no": "110040"},
    "Nagamangala Police Station": {"ward": "050", "reg_no": "110050"},
    "Pandavapura Police Station": {"ward": "060", "reg_no": "110060"},
    "Arakere Police Station": {"ward": "070", "reg_no": "110070"},
    "Basaralu Police Station": {"ward": "080", "reg_no": "110080"},
    "Bellur Police Station": {"ward": "090", "reg_no": "110090"},

    # --- KOLAR (Code 07) ---
    "Kolar Town Police Station": {"ward": "001", "reg_no": "070001"},
    "Kolar Rural Police Station": {"ward": "005", "reg_no": "070005"},
    "Galpet Police Station": {"ward": "006", "reg_no": "070006"},
    "Robertsonpet Police Station (KGF)": {"ward": "010", "reg_no": "070010"},
    "Andersonpet Police Station (KGF)": {"ward": "011", "reg_no": "070011"},
    "Bangarpet Police Station": {"ward": "020", "reg_no": "070020"},
    "Malur Police Station": {"ward": "030", "reg_no": "070030"},
    "Mulbagal Town Police Station": {"ward": "040", "reg_no": "070040"},
    "Srinivaspura Police Station": {"ward": "050", "reg_no": "070050"},
    "Kolar Traffic Police Station": {"ward": "002", "reg_no": "070002"},
    "Vemagal Police Station": {"ward": "060", "reg_no": "070060"},

    # --- CHIKKAMAGALURU (Code 18) ---
    "Chikkamagaluru Town Police Station": {"ward": "001", "reg_no": "180001"},
    "Basavanahalli Police Station": {"ward": "002", "reg_no": "180002"},
    "Chikkamagaluru Rural Police Station": {"ward": "005", "reg_no": "180005"},
    "Aldur Police Station": {"ward": "010", "reg_no": "180010"},
    "Mudigere Police Station": {"ward": "020", "reg_no": "180020"},
    "Koppa Police Station": {"ward": "030", "reg_no": "180030"},
    "Sringeri Police Station": {"ward": "040", "reg_no": "180040"},
    "N.R. Pura Police Station": {"ward": "050", "reg_no": "180050"},
    "Kadur Police Station": {"ward": "060", "reg_no": "180060"},
    "Tarikere Police Station": {"ward": "070", "reg_no": "180070"},
    "Balehonnur Police Station": {"ward": "080", "reg_no": "180080"},

    # --- CHITRADURGA (Code 16) ---
    "Chitradurga Fort Police Station": {"ward": "001", "reg_no": "160001"},
    "Chitradurga Extension Police Station": {"ward": "002", "reg_no": "160002"},
    "Chitradurga Rural Police Station": {"ward": "005", "reg_no": "160005"},
    "Hiriyur Town Police Station": {"ward": "010", "reg_no": "160010"},
    "Challakere Police Station": {"ward": "020", "reg_no": "160020"},
    "Hosadurga Police Station": {"ward": "030", "reg_no": "160030"},
    "Holalkere Police Station": {"ward": "040", "reg_no": "160040"},
    "Molakalmuru Police Station": {"ward": "050", "reg_no": "160050"},
    "Aimangala Police Station": {"ward": "060", "reg_no": "160060"},
    "Chitradurga Traffic Police Station": {"ward": "003", "reg_no": "160003"},
    "Chitradurga Women Police Station": {"ward": "004", "reg_no": "160004"},

    # --- RAICHUR (Code 36) ---
    "Raichur Sadar Bazar Police Station": {"ward": "001", "reg_no": "360001"},
    "Raichur Market Yard Police Station": {"ward": "002", "reg_no": "360002"},
    "Raichur West Circle Police Station": {"ward": "003", "reg_no": "360003"},
    "Raichur Netaji Nagar Police Station": {"ward": "004", "reg_no": "360004"},
    "Raichur Rural Police Station": {"ward": "005", "reg_no": "360005"},
    "Manvi Police Station": {"ward": "010", "reg_no": "360010"},
    "Sindhanur Town Police Station": {"ward": "020", "reg_no": "360020"},
    "Sindhanur Rural Police Station": {"ward": "021", "reg_no": "360021"},
    "Lingsugur Police Station": {"ward": "030", "reg_no": "360030"},
    "Deodurga Police Station": {"ward": "040", "reg_no": "360040"},
    "Maski Police Station": {"ward": "050", "reg_no": "360050"},

    # --- BIDAR (Code 38) ---
    "Bidar Market Police Station": {"ward": "001", "reg_no": "380001"},
    "Bidar Gandhi Gunj Police Station": {"ward": "002", "reg_no": "380002"},
    "Bidar New Town Police Station": {"ward": "003", "reg_no": "380003"},
    "Bidar Rural Police Station": {"ward": "005", "reg_no": "380005"},
    "Basavakalyan Town Police Station": {"ward": "010", "reg_no": "38010"},
    "Humnabad Police Station": {"ward": "020", "reg_no": "38020"},
    "Bhalki Town Police Station": {"ward": "030", "reg_no": "38030"},
    "Aurad Police Station": {"ward": "040", "reg_no": "38040"},
    "Bidar Traffic Police Station": {"ward": "004", "reg_no": "380004"},
    "Bidar Women Police Station": {"ward": "006", "reg_no": "380006"},

    # --- BAGALKOTE (Code 29) ---
    "Bagalkote Town Police Station": {"ward": "001", "reg_no": "290001"},
    "Bagalkote Navanagar Police Station": {"ward": "002", "reg_no": "290002"},
    "Bagalkote Rural Police Station": {"ward": "005", "reg_no": "290005"},
    "Jamkhandi Town Police Station": {"ward": "010", "reg_no": "290010"},
    "Mudhol Police Station": {"ward": "020", "reg_no": "290020"},
    "Badami Police Station": {"ward": "030", "reg_no": "290030"},
    "Hungund Police Station": {"ward": "040", "reg_no": "290040"},
    "Bilagi Police Station": {"ward": "050", "reg_no": "290050"},
    "Ilkal Police Station": {"ward": "060", "reg_no": "290060"},
    "Mahalingpur Police Station": {"ward": "070", "reg_no": "290070"},

    # --- GADAG (Code 26) ---
    "Gadag Town Police Station": {"ward": "001", "reg_no": "260001"},
    "Gadag Rural Police Station": {"ward": "005", "reg_no": "260005"},
    "Betgeri Police Station": {"ward": "002", "reg_no": "260002"},
    "Ron Police Station": {"ward": "010", "reg_no": "260010"},
    "Shirahatti Police Station": {"ward": "020", "reg_no": "260020"},
    "Mundargi Police Station": {"ward": "030", "reg_no": "260030"},
    "Nargund Police Station": {"ward": "040", "reg_no": "260040"},
    "Gajendragad Police Station": {"ward": "050", "reg_no": "260050"},
    "Laxmeshwar Police Station": {"ward": "060", "reg_no": "260060"},

    # --- HAVERI (Code 27) ---
    "Haveri Town Police Station": {"ward": "001", "reg_no": "270001"},
    "Haveri Rural Police Station": {"ward": "005", "reg_no": "270005"},
    "Ranebennur Town Police Station": {"ward": "010", "reg_no": "270010"},
    "Ranebennur Rural Police Station": {"ward": "011", "reg_no": "270011"},
    "Byadgi Police Station": {"ward": "020", "reg_no": "270020"},
    "Hirekerur Police Station": {"ward": "030", "reg_no": "270030"},
    "Shiggaon Police Station": {"ward": "040", "reg_no": "270040"},
    "Hangal Police Station": {"ward": "050", "reg_no": "270050"},
    "Savanur Police Station": {"ward": "060", "reg_no": "270060"},
    "Bankapura Police Station": {"ward": "070", "reg_no": "270070"},

    # --- KOPPAL (Code 37) ---
    "Koppal Town Police Station": {"ward": "001", "reg_no": "370001"},
    "Koppal Rural Police Station": {"ward": "005", "reg_no": "370005"},
    "Gangavathi Town Police Station": {"ward": "010", "reg_no": "370010"},
    "Gangavathi Rural Police Station": {"ward": "011", "reg_no": "370011"},
    "Kushtagi Police Station": {"ward": "020", "reg_no": "370020"},
    "Yelburga Police Station": {"ward": "030", "reg_no": "370030"},
    "Munirabad Police Station": {"ward": "040", "reg_no": "370040"},
    "Karatagi Police Station": {"ward": "050", "reg_no": "370050"},

    # --- YADGIR (Code 33) ---
    "Yadgir Town Police Station": {"ward": "001", "reg_no": "330001"},
    "Yadgir Rural Police Station": {"ward": "005", "reg_no": "330005"},
    "Shahapur Police Station": {"ward": "010", "reg_no": "330010"},
    "Shorapur Police Station": {"ward": "020", "reg_no": "330020"},
    "Gurmitkal Police Station": {"ward": "030", "reg_no": "330030"},
    "Kembhavi Police Station": {"ward": "040", "reg_no": "330040"},

    # --- RAMANAGARA (Code 42) ---
    "Ramanagara Town Police Station": {"ward": "001", "reg_no": "420001"},
    "Ramanagara Rural Police Station": {"ward": "005", "reg_no": "420005"},
    "Ijoor Police Station": {"ward": "002", "reg_no": "420002"},
    "Channapatna Town Police Station": {"ward": "010", "reg_no": "420010"},
    "Kanakapura Town Police Station": {"ward": "020", "reg_no": "420020"},
    "Kanakapura Rural Police Station": {"ward": "021", "reg_no": "420021"},
    "Magadi Police Station": {"ward": "030", "reg_no": "420030"},
    "Bidadi Police Station": {"ward": "040", "reg_no": "420040"},
    "Harohalli Police Station": {"ward": "050", "reg_no": "420050"},

    # --- CHIKKABALLAPURA (Code 40) ---
    "Chikkaballapura Town Police Station": {"ward": "001", "reg_no": "400001"},
    "Chikkaballapura Rural Police Station": {"ward": "005", "reg_no": "400005"},
    "Chintamani Town Police Station": {"ward": "010", "reg_no": "400010"},
    "Sidlaghatta Police Station": {"ward": "020", "reg_no": "400020"},
    "Gauribidanur Town Police Station": {"ward": "030", "reg_no": "400030"},
    "Bagepalli Police Station": {"ward": "040", "reg_no": "400040"},
    "Gudibande Police Station": {"ward": "050", "reg_no": "400050"},
    "Shidlaghatta Rural Police Station": {"ward": "021", "reg_no": "400021"},

    # --- KODAGU (Code 12) ---
    "Madikeri Town Police Station": {"ward": "001", "reg_no": "120001"},
    "Madikeri Rural Police Station": {"ward": "005", "reg_no": "120005"},
    "Virajpet Town Police Station": {"ward": "010", "reg_no": "120010"},
    "Somwarpet Police Station": {"ward": "020", "reg_no": "120020"},
    "Kushalnagar Town Police Station": {"ward": "030", "reg_no": "120030"},
    "Gonikoppa Police Station": {"ward": "040", "reg_no": "120040"},
    "Ponnampet Police Station": {"ward": "050", "reg_no": "120050"},
    "Siddapura Police Station": {"ward": "060", "reg_no": "120060"},

    # --- DAKSHINA KANNADA (Code 21) ---
    "Puttur Town Police Station": {"ward": "001", "reg_no": "210001"},
    "Puttur Rural Police Station": {"ward": "005", "reg_no": "210005"},
    "Dakshina Kannada Puttur Police Station": {"ward": "006", "reg_no": "210006"},
    "Bantwal Town Police Station": {"ward": "010", "reg_no": "210010"},
    "Bantwal Rural Police Station": {"ward": "011", "reg_no": "210011"},
    "Belthangady Police Station": {"ward": "020", "reg_no": "210020"},
    "Sullia Police Station": {"ward": "030", "reg_no": "210030"},
    "Subramanya Police Station": {"ward": "040", "reg_no": "210040"},
    "Uppinangady Police Station": {"ward": "050", "reg_no": "210050"},
    "Vittal Police Station": {"ward": "060", "reg_no": "210060"},
    "Moodbidri Police Station": {"ward": "070", "reg_no": "210070"}
}

STATION_NAMES = sorted(list(POLICE_DATABASE.keys()))

# --- DATABASE CONNECTION ---
def get_mongodb_connection():
    mongodb_uri = app.config['MONGODB_URI']
    print(f"🔗 Connecting to MongoDB Atlas...")
    try:
        client = MongoClient(mongodb_uri, retryWrites=True, w='majority')
        client.admin.command('ismaster')
        print("✅ MongoDB Atlas connection successful!")
        db_name = 'SwiftAid'
        return client, db_name
    except Exception as e:
        print(f"❌ MongoDB Atlas connection failed: {e}")
        raise e

# Initialize MongoDB connection
try:
    client, db_name = get_mongodb_connection()
    db = client[db_name]
    print("✅ Database connection established.")
except Exception as e:
    print(f"❌ Critical Error: {e}")
    exit(1)

# Collections
POLICE_users = db.POLICE_users
incidents_collection = db.incidents
incidents_police_collection = db.incidents_police
police_officers_collection = db.police_officers
assigned_cases_collection = db.ASSIGNED_CASES
police_stations_collection = db.police_stations

# --- DATABASE OPTIMIZATION ---
def init_indexes():
    """Create indexes to speed up queries"""
    try:
        print("🚀 Optimizing database with indexes...")
        incidents_police_collection.create_index([("created_at", -1)])
        incidents_police_collection.create_index([("status", 1)])
        incidents_police_collection.create_index([("severity", 1)])
        incidents_police_collection.create_index([("assigned_officer", 1)])
        
        incidents_collection.create_index([("created_at", -1)])
        incidents_collection.create_index([("status", 1)])
        
        assigned_cases_collection.create_index([("incident_id", 1)])
        assigned_cases_collection.create_index([("assigned_officer", 1)])
        
        POLICE_users.create_index([("username", 1)])
        police_officers_collection.create_index([("police_station", 1)])
        print("✅ Database indexes created successfully!")
    except Exception as e:
        print(f"⚠️ Index creation warning: {e}")

init_indexes()

# Fix existing data issues (Legacy Cleanup)
def fix_existing_null_usernames():
    try:
        police_officers_collection.update_many({'username': None}, {'$set': {'username': ''}})
        police_officers_collection.update_many({'username': {'$exists': False}}, {'$set': {'username': ''}})
    except Exception:
        pass

def fix_police_officers_index():
    try:
        indexes = list(police_officers_collection.list_indexes())
        username_index = next((index for index in indexes if 'username' in index['key']), None)
        if username_index:
            police_officers_collection.drop_index(username_index['name'])
    except Exception:
        pass

fix_police_officers_index()
fix_existing_null_usernames()

# --- LOGIN & AUTHENTICATION ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.email = user_data['email']
        self.role = user_data.get('role', 'police')
        self.police_station = user_data.get('police_station', '')
        self.police_station_reg_no = user_data.get('police_station_reg_no', '')
        self.full_name = user_data.get('full_name', '')
        self.designation = user_data.get('designation', 'Police Officer')
        self.created_at = user_data.get('created_at', datetime.now(IST))

@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = POLICE_users.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
    except Exception:
        pass
    return None

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(hashed_password, password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

# --- HELPER FUNCTIONS ---
def get_address_from_coordinates(lat, lng):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=18&addressdetails=1"
        headers = {'User-Agent': 'SwiftAid Police System/1.0'}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('display_name', 'Address not found')
        return f"Location at {lat}, {lng}"
    except Exception:
        return f"Location at {lat}, {lng}"

def convert_to_ist(dt):
    """Helper to convert any datetime to IST"""
    if not dt: return datetime.now(IST)
    if isinstance(dt, str):
        try: dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except: return datetime.now(IST)
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def process_public_incident(incident):
    """Robustly process public incidents"""
    try:
        incident_id = str(incident.get('_id'))
        lat = float(incident.get('lat') or incident.get('latitude', 0))
        lng = float(incident.get('lng') or incident.get('longitude', 0))
        user_name = incident.get('user_name', 'Unknown User')
        
        incident_type = "Emergency Alert"
        if incident.get('metadata', {}).get('sos_type'):
            incident_type = f"SOS - {incident['metadata']['sos_type'].title()}"
        if incident.get('accel_mag', 0) > 1.5:
            incident_type = "Possible Accident"
        
        severity = "high" if (incident.get('speed', 0) > 0) else ("medium" if incident.get('accel_mag', 0) > 1.0 else "low")
        address = get_address_from_coordinates(lat, lng)
        created_at = convert_to_ist(incident.get('timestamp') or incident.get('created_at'))

        return {
            '_id': incident_id,
            'incident_id': incident.get('incident_id', 'PUB-' + incident_id),
            'title': f"Emergency Alert from {user_name}",
            'description': f"Emergency alert triggered by {user_name}. Type: {incident_type}",
            'incident_type': incident_type,
            'severity': severity,
            'status': 'active',
            'latitude': lat,
            'longitude': lng,
            'address': address,
            'reported_by': user_name,
            'assigned_officer': incident.get('assigned_officer', 'Unassigned'),
            'created_at': created_at,
            'source': 'public'
        }
    except Exception:
        return None

def process_police_incident(incident):
    """Robustly process police incidents"""
    try:
        incident_id = str(incident.get('_id'))
        created_at = convert_to_ist(incident.get('created_at'))
        return {
            '_id': incident_id,
            'incident_id': incident.get('incident_id', 'POL-' + incident_id),
            'title': incident.get('title', 'Untitled Incident'),
            'description': incident.get('description', 'No description'),
            'incident_type': incident.get('incident_type', 'Unknown'),
            'severity': incident.get('severity', 'medium'),
            'status': incident.get('status', 'pending'),
            'latitude': float(incident.get('latitude', 0)),
            'longitude': float(incident.get('longitude', 0)),
            'address': incident.get('address', 'Unknown location'),
            'reported_by': incident.get('reported_by', 'Unknown'),
            'assigned_officer': incident.get('assigned_officer', 'Unassigned'),
            'created_at': created_at,
            'source': 'police'
        }
    except Exception:
        return None

def assign_case_to_officer(incident_id, source, assigned_officer, incident_data):
    try:
        incident_data['assigned_officer'] = assigned_officer
        incident_data['updated_at'] = datetime.now(IST)
        
        assigned_case = {
            'incident_id': incident_id,
            'source_collection': source,
            'assigned_officer': assigned_officer,
            'assigned_by': current_user.username,
            'assigned_at': datetime.now(IST),
            'incident_data': incident_data,
            'status': 'assigned',
            'last_updated': datetime.now(IST)
        }
        result = assigned_cases_collection.insert_one(assigned_case)
        return result.inserted_id
    except Exception as e:
        print(f"Error assigning case: {e}")
        return None

# --- ROUTES ---

@app.route('/')
@login_required
def dashboard():
    try:
        # Fetch ALL incidents from both collections (No Limits for Stats)
        raw_police = list(incidents_police_collection.find().sort('created_at', -1))
        raw_public = list(incidents_collection.find().sort('created_at', -1))
        
        all_incidents = []
        
        # Process and combine
        for i in raw_police:
            d = process_police_incident(i)
            if d:
                assignment = assigned_cases_collection.find_one({'incident_id': str(i['_id'])})
                d['is_assigned'] = assignment is not None
                all_incidents.append(d)
        
        for i in raw_public:
            d = process_public_incident(i)
            if d:
                assignment = assigned_cases_collection.find_one({'incident_id': str(i['_id'])})
                d['is_assigned'] = assignment is not None
                all_incidents.append(d)
        
        # Sort by latest first
        all_incidents.sort(key=lambda x: x['created_at'], reverse=True)
        
        # Calculate Statistics for Dashboard (Fixing "No Numbers" Issue)
        total_incidents = len(all_incidents)
        police_count = sum(1 for x in all_incidents if x['source'] == 'police')
        public_count = sum(1 for x in all_incidents if x['source'] == 'public')
        high_severity_count = sum(1 for x in all_incidents if x['severity'] == 'high')
        
        active_incidents = sum(1 for x in all_incidents if x['status'] == 'active')
        resolved_incidents = sum(1 for x in all_incidents if x['status'] == 'resolved')
        
        assigned_count = sum(1 for x in all_incidents if x['is_assigned'])
        unassigned_count = total_incidents - assigned_count
        
        active_officers = police_officers_collection.count_documents({'status': 'active'})
        user_incidents = sum(1 for x in all_incidents if x.get('assigned_officer') == current_user.username)
        
        # Pass 10 most recent incidents for the list
        recent_list = all_incidents[:10]
        
        return render_template('dashboard.html', 
                             incidents=recent_list,
                             total_incidents=total_incidents,
                             police_count=police_count,
                             public_count=public_count,
                             high_severity_count=high_severity_count,
                             active_incidents=active_incidents,
                             resolved_incidents=resolved_incidents,
                             assigned_count=assigned_count,
                             unassigned_count=unassigned_count,
                             active_officers=active_officers,
                             user_incidents=user_incidents)
    except Exception as e:
        print(f"Dashboard Error: {e}")
        # Return safe empty context to prevent crash
        return render_template('dashboard.html', incidents=[], total_incidents=0, 
                             police_count=0, public_count=0, high_severity_count=0,
                             active_incidents=0, resolved_incidents=0, 
                             assigned_count=0, unassigned_count=0, 
                             active_officers=0, user_incidents=0)

@app.route('/api/get-station-data')
def get_station_data():
    """API for registration form validation"""
    station_name = request.args.get('station')
    if station_name in POLICE_DATABASE:
        return jsonify(POLICE_DATABASE[station_name])
    return jsonify({'error': 'Station not found'}), 404

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        police_station = request.form.get('police_station')
        ward_number = request.form.get('ward_number')
        police_station_reg_no = request.form.get('police_station_reg_no')
        
        if not all([password, confirm_password, police_station, ward_number, police_station_reg_no]):
            flash('All fields are required', 'danger')
            return render_template('register.html', police_stations=STATION_NAMES)
        
        # Validation
        if police_station not in POLICE_DATABASE:
            flash('Invalid Police Station selected.', 'danger')
            return render_template('register.html', police_stations=STATION_NAMES)
            
        real_data = POLICE_DATABASE[police_station]
        if real_data['ward'] != ward_number:
            flash(f"Security Alert: Ward Number mismatch. Expected: {real_data['ward']}", 'danger')
            return render_template('register.html', police_stations=STATION_NAMES)
        if real_data['reg_no'] != police_station_reg_no:
            flash(f"Security Alert: Registration Number mismatch. Expected: {real_data['reg_no']}", 'danger')
            return render_template('register.html', police_stations=STATION_NAMES)

        if POLICE_users.find_one({'police_station_reg_no': police_station_reg_no}):
            flash('Station already registered.', 'danger')
            return render_template('register.html', police_stations=STATION_NAMES)
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html', police_stations=STATION_NAMES)
        
        try:
            base_username = re.sub(r'[^a-zA-Z0-9]', '', police_station).lower()[:15]
            reg_suffix = police_station_reg_no[-4:]
            username = f"{base_username}_{reg_suffix}"
            
            # Ensure unique username
            counter = 1
            original_username = username
            while POLICE_users.find_one({'username': username}):
                username = f"{original_username}_{counter}"
                counter += 1
            
            new_user = {
                'username': username,
                'email': f"{username}@karnatakapolice.gov.in",
                'password_hash': hash_password(password),
                'police_station': police_station,
                'police_station_reg_no': police_station_reg_no,
                'ward_number': ward_number,
                'full_name': police_station,
                'designation': 'Police Station Admin',
                'role': 'police_admin',
                'status': 'active',
                'created_at': datetime.now(IST),
                'last_login': None
            }
            res = POLICE_users.insert_one(new_user)
            
            # Create Officer Profile for Admin
            officer_data = {
                'user_id': res.inserted_id,
                'username': username,
                'email': new_user['email'],
                'police_station': police_station,
                'police_station_reg_no': police_station_reg_no,
                'ward_number': ward_number,
                'full_name': police_station,
                'designation': 'Police Station Admin',
                'status': 'active',
                'created_at': datetime.now(IST)
            }
            police_officers_collection.insert_one(officer_data)
            
            user = User(new_user)
            login_user(user)
            flash(f'Registration successful! Welcome {police_station}!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Registration error: {e}', 'danger')
            
    return render_template('register.html', police_stations=STATION_NAMES)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        police_station = request.form.get('police_station')
        reg_no = request.form.get('police_station_reg_no')
        password = request.form.get('password')
        
        user_data = POLICE_users.find_one({'police_station': police_station, 'police_station_reg_no': reg_no})
        if user_data and check_password(user_data['password_hash'], password):
            user = User(user_data)
            login_user(user)
            POLICE_users.update_one({'_id': user_data['_id']}, {'$set': {'last_login': datetime.now(IST)}})
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    
    return render_template('login.html', registered_stations=STATION_NAMES)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/incidents')
@login_required
def incidents():
    # Same logic as dashboard to get full list
    raw_police = list(incidents_police_collection.find())
    raw_public = list(incidents_collection.find())
    
    all_incidents = []
    for i in raw_police:
        d = process_police_incident(i)
        if d:
            d['is_assigned'] = assigned_cases_collection.find_one({'incident_id': str(i['_id'])}) is not None
            all_incidents.append(d)
    for i in raw_public:
        d = process_public_incident(i)
        if d:
            d['is_assigned'] = assigned_cases_collection.find_one({'incident_id': str(i['_id'])}) is not None
            all_incidents.append(d)
            
    all_incidents.sort(key=lambda x: x['created_at'], reverse=True)
    
    stats = {
        'total_incidents': len(all_incidents),
        'police_count': sum(1 for i in all_incidents if i['source'] == 'police'),
        'public_count': sum(1 for i in all_incidents if i['source'] == 'public'),
        'high_severity_count': sum(1 for i in all_incidents if i['severity'] == 'high'),
        'active_count': sum(1 for i in all_incidents if i['status'] == 'active'),
        'resolved_count': sum(1 for i in all_incidents if i['status'] == 'resolved'),
        'assigned_count': sum(1 for i in all_incidents if i['is_assigned']),
        'unassigned_count': len(all_incidents) - sum(1 for i in all_incidents if i['is_assigned'])
    }
    
    officers = list(police_officers_collection.find({'status': 'active'}))
    return render_template('incidents.html', all_incidents=all_incidents, officers=officers, **stats)

@app.route('/api/incidents', methods=['GET', 'POST'])
@login_required
def api_incidents_route():
    if request.method == 'POST':
        data = request.get_json()
        address = data.get('address')
        if not address and data.get('latitude'):
            address = get_address_from_coordinates(data.get('latitude'), data.get('longitude'))
            
        new_incident = {
            'incident_id': f'POL-{datetime.now(IST).strftime("%Y%m%d-%H%M%S")}',
            'title': data.get('title'),
            'description': data.get('description'),
            'incident_type': data.get('incident_type', 'Other'),
            'severity': data.get('severity', 'medium'),
            'status': 'active',
            'latitude': float(data.get('latitude', 14.4664)),
            'longitude': float(data.get('longitude', 75.9238)),
            'address': address or 'Unknown',
            'reported_by': current_user.username,
            'assigned_officer': data.get('assigned_officer', 'Unassigned'),
            'created_at': datetime.now(IST),
            'source': 'police'
        }
        res = incidents_police_collection.insert_one(new_incident)
        return jsonify({'message': 'Added', 'id': str(res.inserted_id)})
    
    # GET Logic for Maps
    raw_police = list(incidents_police_collection.find())
    raw_public = list(incidents_collection.find())
    data = []
    for i in raw_police:
        d = process_police_incident(i)
        if d: data.append(d)
    for i in raw_public:
        d = process_public_incident(i)
        if d: data.append(d)
    return jsonify(data)

@app.route('/api/incidents/<incident_id>/details')
@login_required
def get_incident_details(incident_id):
    source = request.args.get('source', 'police')
    collection = incidents_police_collection if source == 'police' else incidents_collection
    try:
        inc = collection.find_one({'_id': ObjectId(incident_id)})
        if not inc: return jsonify({'error': 'Not found'}), 404
        
        data = process_police_incident(inc) if source == 'police' else process_public_incident(inc)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/incidents/<incident_id>/assign-officer', methods=['PUT'])
@login_required
def assign_officer_route(incident_id):
    try:
        data = request.get_json()
        source = data.get('source', 'police')
        officer = data.get('assigned_officer')
        
        collection = incidents_police_collection if source == 'police' else incidents_collection
        inc = collection.find_one({'_id': ObjectId(incident_id)})
        if not inc: return jsonify({'error': 'Incident not found'}), 404
        
        proc_inc = process_police_incident(inc) if source == 'police' else process_public_incident(inc)
        
        # Check existing assignment
        existing = assigned_cases_collection.find_one({'incident_id': incident_id})
        if existing:
            assigned_cases_collection.update_one({'_id': existing['_id']}, {
                '$set': {'assigned_officer': officer, 'assigned_by': current_user.username, 'last_updated': datetime.now(IST)}
            })
        else:
            assign_case_to_officer(incident_id, source, officer, proc_inc)
            
        # Update original record too
        collection.update_one({'_id': ObjectId(incident_id)}, {'$set': {'assigned_officer': officer}})
        
        return jsonify({'message': 'Assigned'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/police-officers', methods=['GET', 'POST'])
@login_required
def police_officers_route():
    if request.method == 'POST':
        data = request.get_json()
        station = current_user.police_station
        
        # Validate uniqueness
        if police_officers_collection.find_one({'badge_number': data.get('badge_number')}):
            return jsonify({'error': 'Badge number already exists'}), 400
            
        new_off = {
            'badge_number': data.get('badge_number'),
            'full_name': data.get('full_name'),
            'designation': data.get('designation'),
            'police_station': station,
            'email': data.get('email'),
            'username': f"{data.get('full_name').lower().replace(' ', '')}_{data.get('badge_number')}",
            'phone': data.get('phone', ''),
            'status': 'active',
            'created_at': datetime.now(IST)
        }
        res = police_officers_collection.insert_one(new_off)
        return jsonify({'message': 'Added', 'officer_id': str(res.inserted_id)})

    # GET
    officers = list(police_officers_collection.find({'police_station': current_user.police_station, 'status': 'active'}))
    data = []
    for o in officers:
        data.append({
            '_id': str(o['_id']),
            'username': o.get('username'),
            'full_name': o.get('full_name'),
            'designation': o.get('designation'),
            'badge_number': o.get('badge_number')
        })
    return jsonify(data)

@app.route('/api/recent-activity')
@login_required
def recent_activity():
    # Simple activity feed
    try:
        recs = list(incidents_police_collection.find().sort('created_at', -1).limit(3))
        activities = []
        for r in recs:
            t = convert_to_ist(r.get('created_at'))
            activities.append({
                'text': f"New Incident: {r.get('title')}",
                'time': t.strftime('%H:%M'),
                'color': 'primary',
                'icon': 'fa-exclamation-circle'
            })
        return jsonify({'activities': activities})
    except:
        return jsonify({'activities': []})

@app.route('/reports/export/csv')
@login_required
def export_csv():
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Source', 'Incident ID', 'Title', 'Type', 'Severity', 'Status', 'Address', 'Reported By', 'Created At'])
        
        for i in incidents_police_collection.find():
            d = process_police_incident(i)
            writer.writerow(['Police', d['incident_id'], d['title'], d['incident_type'], d['severity'], d['status'], d['address'], d['reported_by'], d['created_at']])
            
        for i in incidents_collection.find():
            d = process_public_incident(i)
            writer.writerow(['Public', d['incident_id'], d['title'], d['incident_type'], d['severity'], d['status'], d['address'], d['reported_by'], d['created_at']])
            
        return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=swiftaid_incidents.csv"})
    except Exception as e:
        flash(f"Export error: {e}", "danger")
        return redirect(url_for('reports'))

@app.route('/reports/export/excel')
@login_required
def export_excel():
    try:
        output = io.BytesIO()
        output.write(b'\xef\xbb\xbf')
        text_output = io.TextIOWrapper(output, encoding='utf-8', newline='')
        writer = csv.writer(text_output)
        writer.writerow(['Source', 'Incident ID', 'Title', 'Type', 'Severity', 'Status', 'Address', 'Reported By', 'Created At'])
        
        for i in incidents_police_collection.find():
            d = process_police_incident(i)
            writer.writerow(['Police', d['incident_id'], d['title'], d['incident_type'], d['severity'], d['status'], d['address'], d['reported_by'], d['created_at']])
            
        for i in incidents_collection.find():
            d = process_public_incident(i)
            writer.writerow(['Public', d['incident_id'], d['title'], d['incident_type'], d['severity'], d['status'], d['address'], d['reported_by'], d['created_at']])
            
        text_output.flush()
        return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=swiftaid_incidents_excel.csv"})
    except Exception:
        return redirect(url_for('reports'))

@app.route('/reports/export/pdf')
@login_required
def export_pdf():
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        elements = []
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=30, alignment=1, textColor=colors.HexColor('#0d6efd'))
        
        elements.append(Paragraph("SWIFTAID POLICE DEPARTMENT - INCIDENTS REPORT", title_style))
        elements.append(Paragraph(f"Generated on: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}", styles["Normal"]))
        elements.append(Spacer(1, 20))
        
        # Police Section
        elements.append(Paragraph("POLICE INCIDENTS", styles['Heading2']))
        data = [['ID', 'Title', 'Severity', 'Status', 'Date']]
        for i in incidents_police_collection.find().sort('created_at', -1):
            d = process_police_incident(i)
            data.append([d['incident_id'][:12], d['title'][:50], d['severity'].title(), d['status'].title(), d['created_at'].strftime('%m/%d %H:%M')])
        
        t = Table(data, colWidths=[1.1*inch, 3.0*inch, 0.7*inch, 0.7*inch, 1.1*inch])
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        
        # Public Section
        elements.append(Paragraph("PUBLIC INCIDENTS", styles['Heading2']))
        data2 = [['ID', 'Title', 'Severity', 'Status', 'Date']]
        for i in incidents_collection.find().sort('created_at', -1):
            d = process_public_incident(i)
            data2.append([d['incident_id'][:12], d['title'][:50], d['severity'].title(), d['status'].title(), d['created_at'].strftime('%m/%d %H:%M')])
            
        t2 = Table(data2, colWidths=[1.1*inch, 3.0*inch, 0.7*inch, 0.7*inch, 1.1*inch])
        t2.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c757d')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
        elements.append(t2)

        doc.build(elements)
        return Response(buffer.getvalue(), mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=swiftaid_report.pdf'})
    except Exception as e:
        print(f"PDF Error: {e}")
        return redirect(url_for('reports'))

@app.route('/api/database-stats')
@login_required
def database_stats():
    return jsonify({'status': 'ok'})

@app.route('/api/profile', methods=['PUT'])
@login_required
def profile_update():
    try:
        data = request.get_json()
        update_data = {
            'email': data.get('email'),
            'full_name': data.get('full_name'),
            'designation': data.get('designation'),
            'ward_number': data.get('ward_number')
        }
        POLICE_users.update_one({'_id': ObjectId(current_user.id)}, {'$set': update_data})
        return jsonify({'message': 'Profile updated'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/profile')
@login_required
def profile():
    user = POLICE_users.find_one({'_id': ObjectId(current_user.id)})
    return render_template('profile.html', user=user)

@app.route('/reports')
@login_required
def reports():
    total_police = incidents_police_collection.count_documents({})
    total_public = incidents_collection.count_documents({})
    active = incidents_police_collection.count_documents({'status': 'active'}) + incidents_collection.count_documents({'status': 'active'})
    resolved = incidents_police_collection.count_documents({'status': 'resolved'}) + incidents_collection.count_documents({'status': 'resolved'}) + db.resolved_cases.count_documents({})
    high = incidents_police_collection.count_documents({'severity': 'high'}) + incidents_collection.count_documents({'severity': 'high'})
    
    stats = {
        'total': total_police+total_public,
        'active': active,
        'resolved': resolved,
        'high_severity': high
    }
    return render_template('reports.html', stats=stats, current_time=datetime.now(IST).strftime('%Y-%m-%d %H:%M'))

if __name__ == '__main__':
    print("🚀 Starting SwiftAid Police Dashboard with FULL DATABASE (Un-optimized Length)...")
    app.run(debug=True)
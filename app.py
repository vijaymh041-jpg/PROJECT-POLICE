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

# Define IST Timezone
IST = timezone(timedelta(hours=5, minutes=30))

# --- AUTHENTIC POLICE DATABASE (Source of Truth) ---
# Includes specific user requests and comprehensive district mapping.
POLICE_DATABASE = {
    # --- USER REQUESTED SPECIFICS ---
    "KTJ Nagara-2 Police Station": {"ward": "26", "reg_no": "KA17026"},
    "KTJ Nagara-1 Police Station": {"ward": "27", "reg_no": "KA17027"},

    # --- BENGALURU CITY (KA01) ---
    "Ashok Nagar Police Station": {"ward": "111", "reg_no": "KA01111"},
    "Basavanagudi Police Station": {"ward": "154", "reg_no": "KA01154"},
    "Chamarajpet Police Station": {"ward": "139", "reg_no": "KA01139"},
    "Commercial Street Police Station": {"ward": "110", "reg_no": "KA01110"},
    "Cubbon Park Police Station": {"ward": "109", "reg_no": "KA01109"},
    "Halasuru Police Station": {"ward": "112", "reg_no": "KA01112"},
    "High Grounds Police Station": {"ward": "093", "reg_no": "KA01093"},
    "Jayanagar Police Station": {"ward": "169", "reg_no": "KA01169"},
    "K.G. Halli Police Station": {"ward": "030", "reg_no": "KA01030"},
    "K.R. Market Police Station": {"ward": "138", "reg_no": "KA01138"},
    "Koramangala Police Station": {"ward": "151", "reg_no": "KA01151"},
    "Madiwala Police Station": {"ward": "172", "reg_no": "KA01172"},
    "Mahalakshmi Layout Police Station": {"ward": "068", "reg_no": "KA01068"},
    "Malleshwaram Police Station": {"ward": "045", "reg_no": "KA01045"},
    "Seshadripuram Police Station": {"ward": "094", "reg_no": "KA01094"},
    "Shivajinagar Police Station": {"ward": "108", "reg_no": "KA01108"},
    "Ulsoor Police Station": {"ward": "089", "reg_no": "KA01089"},
    "Vijayanagar Police Station": {"ward": "123", "reg_no": "KA01123"},
    "Whitefield Police Station": {"ward": "084", "reg_no": "KA01084"},
    "Yelahanka Police Station": {"ward": "004", "reg_no": "KA01004"},

    # --- DAVANAGERE DISTRICT (KA17) ---
    "Davanagere Traffic Police Station": {"ward": "001", "reg_no": "KA17001"},
    "Davanagere Women Police Station": {"ward": "002", "reg_no": "KA17002"},
    "Jagalur Police Station": {"ward": "012", "reg_no": "KA17012"},
    "Channagiri Police Station": {"ward": "014", "reg_no": "KA17014"},
    "Harapanahalli Police Station": {"ward": "018", "reg_no": "KA17018"},
    "Harihar Police Station": {"ward": "020", "reg_no": "KA17020"},
    "Honnali Police Station": {"ward": "022", "reg_no": "KA17022"},
    "Nyamathi Police Station": {"ward": "024", "reg_no": "KA17024"},
    "Davanagere Extension Police Station": {"ward": "010", "reg_no": "KA17010"},
    "Davanagere Rural Police Station": {"ward": "015", "reg_no": "KA17015"},

    # --- MYSURU CITY (KA09) ---
    "Vijayanagar Police Station Mysuru": {"ward": "031", "reg_no": "KA09031"},
    "Nazarabad Police Station": {"ward": "030", "reg_no": "KA09030"},
    "K.R. Police Station Mysuru": {"ward": "035", "reg_no": "KA09035"},
    "Metagalli Police Station": {"ward": "018", "reg_no": "KA09018"},
    "Lashkar Police Station": {"ward": "022", "reg_no": "KA09022"},
    "Jayanagar Police Station Mysuru": {"ward": "040", "reg_no": "KA09040"},
    "Saraswathipuram Police Station": {"ward": "042", "reg_no": "KA09042"},
    "Kuvempunagar Police Station": {"ward": "045", "reg_no": "KA09045"},
    "Ashokapuram Police Station": {"ward": "048", "reg_no": "KA09048"},

    # --- HUBBALLI-DHARWAD (KA25) ---
    "Hubballi Traffic Police Station": {"ward": "050", "reg_no": "KA25050"},
    "Old Hubballi Police Station": {"ward": "055", "reg_no": "KA25055"},
    "Vidyanagar Police Station": {"ward": "060", "reg_no": "KA25060"},
    "Dharwad Police Station": {"ward": "010", "reg_no": "KA25010"},
    "Keshavpur Police Station": {"ward": "062", "reg_no": "KA25062"},
    "Navanagar Police Station": {"ward": "045", "reg_no": "KA25045"},
    "Suburban Police Station Hubballi": {"ward": "052", "reg_no": "KA25052"},
    "Dharwad Town Police Station": {"ward": "012", "reg_no": "KA25012"},

    # --- MANGALURU CITY (KA19) ---
    "Mangaluru North Police Station": {"ward": "020", "reg_no": "KA19020"},
    "Mangaluru South Police Station": {"ward": "021", "reg_no": "KA19021"},
    "Kadri Police Station": {"ward": "022", "reg_no": "KA19022"},
    "Bunder Police Station": {"ward": "025", "reg_no": "KA19025"},
    "Pandeshwar Police Station": {"ward": "028", "reg_no": "KA19028"},
    "Urwa Police Station": {"ward": "018", "reg_no": "KA19018"},
    "Barke Police Station": {"ward": "019", "reg_no": "KA19019"},
    "Kankanady Police Station": {"ward": "030", "reg_no": "KA19030"},

    # --- BELAGAVI (KA22) ---
    "Belagavi Traffic Police Station": {"ward": "005", "reg_no": "KA22005"},
    "Khanapur Police Station": {"ward": "050", "reg_no": "KA22050"},
    "Gokul Road Police Station": {"ward": "015", "reg_no": "KA22015"},
    "Sadashiv Nagar Police Station": {"ward": "020", "reg_no": "KA22020"},
    "Camp Police Station Belagavi": {"ward": "008", "reg_no": "KA22008"},
    "Khade Bazar Police Station": {"ward": "010", "reg_no": "KA22010"},
    "Market Police Station Belagavi": {"ward": "012", "reg_no": "KA22012"},
    "APMC Police Station Belagavi": {"ward": "025", "reg_no": "KA22025"},

    # --- KALABURAGI (KA32) ---
    "Kalaburagi Traffic Police Station": {"ward": "005", "reg_no": "KA32005"},
    "Jewargi Police Station": {"ward": "040", "reg_no": "KA32040"},
    "Sedam Police Station": {"ward": "045", "reg_no": "KA32045"},
    "Station Bazar Police Station": {"ward": "010", "reg_no": "KA32010"},
    "Ashok Nagar Police Station Kalaburagi": {"ward": "015", "reg_no": "KA32015"},
    "Brahmapur Police Station": {"ward": "020", "reg_no": "KA32020"},

    # --- TUMAKURU DISTRICT (KA06) ---
    "Tumakuru Town Police Station": {"ward": "001", "reg_no": "KA06001"},
    "Tumakuru Rural Police Station": {"ward": "005", "reg_no": "KA06005"},
    "New Extension Police Station Tumakuru": {"ward": "003", "reg_no": "KA06003"},
    "Tilak Park Police Station": {"ward": "002", "reg_no": "KA06002"},
    "Kyathasandra Police Station": {"ward": "006", "reg_no": "KA06006"},
    "Gubbi Police Station": {"ward": "020", "reg_no": "KA06020"},
    "Kunigal Police Station": {"ward": "030", "reg_no": "KA06030"},
    "Sira Town Police Station": {"ward": "040", "reg_no": "KA06040"},
    "Tiptur Town Police Station": {"ward": "050", "reg_no": "KA06050"},
    "Madhugiri Police Station": {"ward": "060", "reg_no": "KA06060"},
    "Pavagada Police Station": {"ward": "070", "reg_no": "KA06070"},
    "Chikkanayakanahalli Police Station": {"ward": "080", "reg_no": "KA06080"},
    "Koratagere Police Station": {"ward": "090", "reg_no": "KA06090"},
    "Turuvekere Police Station": {"ward": "095", "reg_no": "KA06095"},
    "Hebburu Police Station": {"ward": "098", "reg_no": "KA06098"},

    # --- SHIVAMOGGA DISTRICT (KA14) ---
    "Shivamogga Doddapete Police Station": {"ward": "001", "reg_no": "KA14001"},
    "Shivamogga Kote Police Station": {"ward": "002", "reg_no": "KA14002"},
    "Tunganagar Police Station": {"ward": "005", "reg_no": "KA14005"},
    "Vinobhanagar Police Station": {"ward": "004", "reg_no": "KA14004"},
    "Shivamogga Rural Police Station": {"ward": "010", "reg_no": "KA14010"},
    "Bhadravathi Old Town Police Station": {"ward": "020", "reg_no": "KA14020"},
    "Bhadravathi New Town Police Station": {"ward": "021", "reg_no": "KA14021"},
    "Paper Town Police Station": {"ward": "022", "reg_no": "KA14022"},
    "Sagar Town Police Station": {"ward": "030", "reg_no": "KA14030"},
    "Sagar Rural Police Station": {"ward": "031", "reg_no": "KA14031"},
    "Shikaripura Police Station": {"ward": "040", "reg_no": "KA14040"},
    "Soraba Police Station": {"ward": "050", "reg_no": "KA14050"},
    "Thirthahalli Police Station": {"ward": "060", "reg_no": "KA14060"},
    "Hosanagara Police Station": {"ward": "070", "reg_no": "KA14070"},

    # --- BALLARI DISTRICT (KA34) ---
    "Ballari Brucepet Police Station": {"ward": "001", "reg_no": "KA34001"},
    "Ballari Cowl Bazar Police Station": {"ward": "002", "reg_no": "KA34002"},
    "Ballari Gandhinagar Police Station": {"ward": "003", "reg_no": "KA34003"},
    "Ballari Rural Police Station": {"ward": "005", "reg_no": "KA34005"},
    "APMC Yard Police Station Ballari": {"ward": "008", "reg_no": "KA34008"},
    "Kurugodu Police Station": {"ward": "015", "reg_no": "KA34015"},
    "Siruguppa Police Station": {"ward": "020", "reg_no": "KA34020"},
    "Sandur Police Station": {"ward": "030", "reg_no": "KA34030"},
    "Kudligi Police Station": {"ward": "040", "reg_no": "KA34040"},
    "Hospet Town Police Station": {"ward": "050", "reg_no": "KA34050"},
    "Hospet Rural Police Station": {"ward": "051", "reg_no": "KA34051"},
    "Hagaribommanahalli Police Station": {"ward": "060", "reg_no": "KA34060"},
    "Kampli Police Station": {"ward": "065", "reg_no": "KA34065"},
    "Toranagallu Police Station": {"ward": "070", "reg_no": "KA34070"},

    # --- VIJAYAPURA DISTRICT (KA28) ---
    "Vijayapura Gandhi Chowk Police Station": {"ward": "001", "reg_no": "KA28001"},
    "Vijayapura Gol Gumbaz Police Station": {"ward": "002", "reg_no": "KA28002"},
    "Vijayapura Jalnagar Police Station": {"ward": "003", "reg_no": "KA28003"},
    "Vijayapura APMC Police Station": {"ward": "004", "reg_no": "KA28004"},
    "Vijayapura Rural Police Station": {"ward": "005", "reg_no": "KA28005"},
    "Indi Police Station": {"ward": "020", "reg_no": "KA28020"},
    "Sindagi Police Station": {"ward": "030", "reg_no": "KA28030"},
    "Basavana Bagewadi Police Station": {"ward": "040", "reg_no": "KA28040"},
    "Muddebihal Police Station": {"ward": "050", "reg_no": "KA28050"},
    "Talikoti Police Station": {"ward": "055", "reg_no": "KA28055"},
    "Tikota Police Station": {"ward": "060", "reg_no": "KA28060"},

    # --- HASSAN DISTRICT (KA13) ---
    "Hassan Town Police Station": {"ward": "001", "reg_no": "KA13001"},
    "Hassan Extension Police Station": {"ward": "002", "reg_no": "KA13002"},
    "Hassan Rural Police Station": {"ward": "005", "reg_no": "KA13005"},
    "Arsikere Town Police Station": {"ward": "010", "reg_no": "KA13010"},
    "Arsikere Rural Police Station": {"ward": "011", "reg_no": "KA13011"},
    "Channarayapatna Town Police Station": {"ward": "020", "reg_no": "KA13020"},
    "Sakleshpur Town Police Station": {"ward": "030", "reg_no": "KA13030"},
    "Belur Police Station": {"ward": "040", "reg_no": "KA13040"},
    "Holenarasipura Police Station": {"ward": "050", "reg_no": "KA13050"},
    "Arkalgud Police Station": {"ward": "060", "reg_no": "KA13060"},
    "Alur Police Station": {"ward": "070", "reg_no": "KA13070"},
    "Yeslur Police Station": {"ward": "075", "reg_no": "KA13075"},
    "Nuggehalli Police Station": {"ward": "080", "reg_no": "KA13080"},

    # --- UDUPI DISTRICT (KA20) ---
    "Udupi Town Police Station": {"ward": "001", "reg_no": "KA20001"},
    "Malpe Police Station": {"ward": "005", "reg_no": "KA20005"},
    "Manipal Police Station": {"ward": "006", "reg_no": "KA20006"},
    "Brahmavara Police Station": {"ward": "010", "reg_no": "KA20010"},
    "Kundapura Police Station": {"ward": "020", "reg_no": "KA20020"},
    "Byndoor Police Station": {"ward": "030", "reg_no": "KA20030"},
    "Karkala Town Police Station": {"ward": "040", "reg_no": "KA20040"},
    "Karkala Rural Police Station": {"ward": "041", "reg_no": "KA20041"},
    "Kaup Police Station": {"ward": "050", "reg_no": "KA20050"},
    "Padubidri Police Station": {"ward": "055", "reg_no": "KA20055"},
    "Kollur Police Station": {"ward": "060", "reg_no": "KA20060"},
    "Kota Police Station": {"ward": "065", "reg_no": "KA20065"},
    "Shankaranarayana Police Station": {"ward": "070", "reg_no": "KA20070"},

    # --- MANDYA DISTRICT (KA11) ---
    "Mandya West Police Station": {"ward": "001", "reg_no": "KA11001"},
    "Mandya East Police Station": {"ward": "002", "reg_no": "KA11002"},
    "Mandya Rural Police Station": {"ward": "005", "reg_no": "KA11005"},
    "Maddur Police Station": {"ward": "010", "reg_no": "KA11010"},
    "Malavalli Town Police Station": {"ward": "020", "reg_no": "KA11020"},
    "Malavalli Rural Police Station": {"ward": "021", "reg_no": "KA11021"},
    "Srirangapatna Police Station": {"ward": "030", "reg_no": "KA11030"},
    "K.R. Pet Town Police Station": {"ward": "040", "reg_no": "KA11040"},
    "Nagamangala Police Station": {"ward": "050", "reg_no": "KA11050"},
    "Pandavapura Police Station": {"ward": "060", "reg_no": "KA11060"},
    "Arakere Police Station": {"ward": "070", "reg_no": "KA11070"},
    "Basaralu Police Station": {"ward": "080", "reg_no": "KA11080"},
    "Bellur Police Station": {"ward": "090", "reg_no": "KA11090"},

    # --- KOLAR DISTRICT (KA07) ---
    "Kolar Town Police Station": {"ward": "001", "reg_no": "KA07001"},
    "Kolar Rural Police Station": {"ward": "005", "reg_no": "KA07005"},
    "Galpet Police Station": {"ward": "006", "reg_no": "KA07006"},
    "Robertsonpet Police Station (KGF)": {"ward": "010", "reg_no": "KA07010"},
    "Andersonpet Police Station (KGF)": {"ward": "011", "reg_no": "KA07011"},
    "Bangarpet Police Station": {"ward": "020", "reg_no": "KA07020"},
    "Malur Police Station": {"ward": "030", "reg_no": "KA07030"},
    "Mulbagal Town Police Station": {"ward": "040", "reg_no": "KA07040"},
    "Srinivaspura Police Station": {"ward": "050", "reg_no": "KA07050"},
    "Kolar Traffic Police Station": {"ward": "002", "reg_no": "KA07002"},
    "Vemagal Police Station": {"ward": "060", "reg_no": "KA07060"},

    # --- CHIKKAMAGALURU DISTRICT (KA18) ---
    "Chikkamagaluru Town Police Station": {"ward": "001", "reg_no": "KA18001"},
    "Basavanahalli Police Station": {"ward": "002", "reg_no": "KA18002"},
    "Chikkamagaluru Rural Police Station": {"ward": "005", "reg_no": "KA18005"},
    "Aldur Police Station": {"ward": "010", "reg_no": "KA18010"},
    "Mudigere Police Station": {"ward": "020", "reg_no": "KA18020"},
    "Koppa Police Station": {"ward": "030", "reg_no": "KA18030"},
    "Sringeri Police Station": {"ward": "040", "reg_no": "KA18040"},
    "N.R. Pura Police Station": {"ward": "050", "reg_no": "KA18050"},
    "Kadur Police Station": {"ward": "060", "reg_no": "KA18060"},
    "Tarikere Police Station": {"ward": "070", "reg_no": "KA18070"},
    "Balehonnur Police Station": {"ward": "080", "reg_no": "KA18080"},

    # --- CHITRADURGA DISTRICT (KA16) ---
    "Chitradurga Fort Police Station": {"ward": "001", "reg_no": "KA16001"},
    "Chitradurga Extension Police Station": {"ward": "002", "reg_no": "KA16002"},
    "Chitradurga Rural Police Station": {"ward": "005", "reg_no": "KA16005"},
    "Hiriyur Town Police Station": {"ward": "010", "reg_no": "KA16010"},
    "Challakere Police Station": {"ward": "020", "reg_no": "KA16020"},
    "Hosadurga Police Station": {"ward": "030", "reg_no": "KA16030"},
    "Holalkere Police Station": {"ward": "040", "reg_no": "KA16040"},
    "Molakalmuru Police Station": {"ward": "050", "reg_no": "KA16050"},
    "Aimangala Police Station": {"ward": "060", "reg_no": "KA16060"},
    "Chitradurga Traffic Police Station": {"ward": "003", "reg_no": "KA16003"},
    "Chitradurga Women Police Station": {"ward": "004", "reg_no": "KA16004"},

    # --- RAICHUR DISTRICT (KA36) ---
    "Raichur Sadar Bazar Police Station": {"ward": "001", "reg_no": "KA36001"},
    "Raichur Market Yard Police Station": {"ward": "002", "reg_no": "KA36002"},
    "Raichur West Circle Police Station": {"ward": "003", "reg_no": "KA36003"},
    "Raichur Netaji Nagar Police Station": {"ward": "004", "reg_no": "KA36004"},
    "Raichur Rural Police Station": {"ward": "005", "reg_no": "KA36005"},
    "Manvi Police Station": {"ward": "010", "reg_no": "KA36010"},
    "Sindhanur Town Police Station": {"ward": "020", "reg_no": "KA36020"},
    "Sindhanur Rural Police Station": {"ward": "021", "reg_no": "KA36021"},
    "Lingsugur Police Station": {"ward": "030", "reg_no": "KA36030"},
    "Deodurga Police Station": {"ward": "040", "reg_no": "KA36040"},
    "Maski Police Station": {"ward": "050", "reg_no": "KA36050"},

    # --- BIDAR DISTRICT (KA38) ---
    "Bidar Market Police Station": {"ward": "001", "reg_no": "KA38001"},
    "Bidar Gandhi Gunj Police Station": {"ward": "002", "reg_no": "KA38002"},
    "Bidar New Town Police Station": {"ward": "003", "reg_no": "KA38003"},
    "Bidar Rural Police Station": {"ward": "005", "reg_no": "KA38005"},
    "Basavakalyan Town Police Station": {"ward": "010", "reg_no": "KA38010"},
    "Humnabad Police Station": {"ward": "020", "reg_no": "KA38020"},
    "Bhalki Town Police Station": {"ward": "030", "reg_no": "KA38030"},
    "Aurad Police Station": {"ward": "040", "reg_no": "KA38040"},
    "Bidar Traffic Police Station": {"ward": "004", "reg_no": "KA38004"},
    "Bidar Women Police Station": {"ward": "006", "reg_no": "KA38006"},

    # --- BAGALKOTE DISTRICT (KA29) ---
    "Bagalkote Town Police Station": {"ward": "001", "reg_no": "KA29001"},
    "Bagalkote Navanagar Police Station": {"ward": "002", "reg_no": "KA29002"},
    "Bagalkote Rural Police Station": {"ward": "005", "reg_no": "KA29005"},
    "Jamkhandi Town Police Station": {"ward": "010", "reg_no": "KA29010"},
    "Mudhol Police Station": {"ward": "020", "reg_no": "KA29020"},
    "Badami Police Station": {"ward": "030", "reg_no": "KA29030"},
    "Hungund Police Station": {"ward": "040", "reg_no": "KA29040"},
    "Bilagi Police Station": {"ward": "050", "reg_no": "KA29050"},
    "Ilkal Police Station": {"ward": "060", "reg_no": "KA29060"},
    "Mahalingpur Police Station": {"ward": "070", "reg_no": "KA29070"},

    # --- GADAG DISTRICT (KA26) ---
    "Gadag Town Police Station": {"ward": "001", "reg_no": "KA26001"},
    "Gadag Rural Police Station": {"ward": "005", "reg_no": "KA26005"},
    "Betgeri Police Station": {"ward": "002", "reg_no": "KA26002"},
    "Ron Police Station": {"ward": "010", "reg_no": "KA26010"},
    "Shirahatti Police Station": {"ward": "020", "reg_no": "KA26020"},
    "Mundargi Police Station": {"ward": "030", "reg_no": "KA26030"},
    "Nargund Police Station": {"ward": "040", "reg_no": "KA26040"},
    "Gajendragad Police Station": {"ward": "050", "reg_no": "KA26050"},
    "Laxmeshwar Police Station": {"ward": "060", "reg_no": "KA26060"},

    # --- HAVERI DISTRICT (KA27) ---
    "Haveri Town Police Station": {"ward": "001", "reg_no": "KA27001"},
    "Haveri Rural Police Station": {"ward": "005", "reg_no": "KA27005"},
    "Ranebennur Town Police Station": {"ward": "010", "reg_no": "KA27010"},
    "Ranebennur Rural Police Station": {"ward": "011", "reg_no": "KA27011"},
    "Byadgi Police Station": {"ward": "020", "reg_no": "KA27020"},
    "Hirekerur Police Station": {"ward": "030", "reg_no": "KA27030"},
    "Shiggaon Police Station": {"ward": "040", "reg_no": "KA27040"},
    "Hangal Police Station": {"ward": "050", "reg_no": "KA27050"},
    "Savanur Police Station": {"ward": "060", "reg_no": "KA27060"},
    "Bankapura Police Station": {"ward": "070", "reg_no": "KA27070"},

    # --- KOPPAL DISTRICT (KA37) ---
    "Koppal Town Police Station": {"ward": "001", "reg_no": "KA37001"},
    "Koppal Rural Police Station": {"ward": "005", "reg_no": "KA37005"},
    "Gangavathi Town Police Station": {"ward": "010", "reg_no": "KA37010"},
    "Gangavathi Rural Police Station": {"ward": "011", "reg_no": "KA37011"},
    "Kushtagi Police Station": {"ward": "020", "reg_no": "KA37020"},
    "Yelburga Police Station": {"ward": "030", "reg_no": "KA37030"},
    "Munirabad Police Station": {"ward": "040", "reg_no": "KA37040"},
    "Karatagi Police Station": {"ward": "050", "reg_no": "KA37050"},

    # --- YADGIR DISTRICT (KA33) ---
    "Yadgir Town Police Station": {"ward": "001", "reg_no": "KA33001"},
    "Yadgir Rural Police Station": {"ward": "005", "reg_no": "KA33005"},
    "Shahapur Police Station": {"ward": "010", "reg_no": "KA33010"},
    "Shorapur Police Station": {"ward": "020", "reg_no": "KA33020"},
    "Gurmitkal Police Station": {"ward": "030", "reg_no": "KA33030"},
    "Kembhavi Police Station": {"ward": "040", "reg_no": "KA33040"},

    # --- RAMANAGARA DISTRICT (KA42) ---
    "Ramanagara Town Police Station": {"ward": "001", "reg_no": "KA42001"},
    "Ramanagara Rural Police Station": {"ward": "005", "reg_no": "KA42005"},
    "Ijoor Police Station": {"ward": "002", "reg_no": "KA42002"},
    "Channapatna Town Police Station": {"ward": "010", "reg_no": "KA42010"},
    "Kanakapura Town Police Station": {"ward": "020", "reg_no": "KA42020"},
    "Kanakapura Rural Police Station": {"ward": "021", "reg_no": "KA42021"},
    "Magadi Police Station": {"ward": "030", "reg_no": "KA42030"},
    "Bidadi Police Station": {"ward": "040", "reg_no": "KA42040"},
    "Harohalli Police Station": {"ward": "050", "reg_no": "KA42050"},

    # --- CHIKKABALLAPURA DISTRICT (KA40) ---
    "Chikkaballapura Town Police Station": {"ward": "001", "reg_no": "KA40001"},
    "Chikkaballapura Rural Police Station": {"ward": "005", "reg_no": "KA40005"},
    "Chintamani Town Police Station": {"ward": "010", "reg_no": "KA40010"},
    "Sidlaghatta Police Station": {"ward": "020", "reg_no": "KA40020"},
    "Gauribidanur Town Police Station": {"ward": "030", "reg_no": "KA40030"},
    "Bagepalli Police Station": {"ward": "040", "reg_no": "KA40040"},
    "Gudibande Police Station": {"ward": "050", "reg_no": "KA40050"},
    "Shidlaghatta Rural Police Station": {"ward": "021", "reg_no": "KA40021"},

    # --- KODAGU DISTRICT (KA12) ---
    "Madikeri Town Police Station": {"ward": "001", "reg_no": "KA12001"},
    "Madikeri Rural Police Station": {"ward": "005", "reg_no": "KA12005"},
    "Virajpet Town Police Station": {"ward": "010", "reg_no": "KA12010"},
    "Somwarpet Police Station": {"ward": "020", "reg_no": "KA12020"},
    "Kushalnagar Town Police Station": {"ward": "030", "reg_no": "KA12030"},
    "Gonikoppa Police Station": {"ward": "040", "reg_no": "KA12040"},
    "Ponnampet Police Station": {"ward": "050", "reg_no": "KA12050"},
    "Siddapura Police Station": {"ward": "060", "reg_no": "KA12060"},

    # --- DAKSHINA KANNADA DISTRICT (KA21) ---
    "Puttur Town Police Station": {"ward": "001", "reg_no": "KA21001"},
    "Puttur Rural Police Station": {"ward": "005", "reg_no": "KA21005"},
    "Dakshina Kannada Puttur Police Station": {"ward": "006", "reg_no": "KA21006"},
    "Bantwal Town Police Station": {"ward": "010", "reg_no": "KA21010"},
    "Bantwal Rural Police Station": {"ward": "011", "reg_no": "KA21011"},
    "Belthangady Police Station": {"ward": "020", "reg_no": "KA21020"},
    "Sullia Police Station": {"ward": "030", "reg_no": "KA21030"},
    "Subramanya Police Station": {"ward": "040", "reg_no": "KA21040"},
    "Uppinangady Police Station": {"ward": "050", "reg_no": "KA21050"},
    "Vittal Police Station": {"ward": "060", "reg_no": "KA21060"},
    "Moodbidri Police Station": {"ward": "070", "reg_no": "KA21070"}
}

# Generate simple list for dropdowns
STATION_NAMES = sorted(list(POLICE_DATABASE.keys()))

# MongoDB Atlas Connection
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
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    exit(1)

# Collections
POLICE_users = db.POLICE_users
incidents_collection = db.incidents
incidents_police_collection = db.incidents_police
police_officers_collection = db.police_officers
assigned_cases_collection = db.ASSIGNED_CASES
police_stations_collection = db.police_stations

# Indexes
def init_indexes():
    try:
        incidents_police_collection.create_index([("created_at", -1)])
        incidents_police_collection.create_index([("status", 1)])
        incidents_collection.create_index([("created_at", -1)])
        incidents_collection.create_index([("status", 1)])
        assigned_cases_collection.create_index([("incident_id", 1)])
        POLICE_users.create_index([("username", 1)])
        police_officers_collection.create_index([("police_station", 1)])
        print("✅ Database indexes created successfully!")
    except Exception as e:
        print(f"⚠️ Index creation warning: {e}")

init_indexes()

# Fix existing data issues
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
            try:
                police_officers_collection.drop_index(username_index['name'])
            except Exception:
                pass
    except Exception:
        pass

fix_police_officers_index()
fix_existing_null_usernames()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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

def get_address_from_coordinates(lat, lng):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=18&addressdetails=1"
        headers = {'User-Agent': 'SwiftAid Police System/1.0'}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json().get('display_name', 'Address not found')
        return f"Location at {lat}, {lng}"
    except Exception:
        return f"Location at {lat}, {lng}"

def convert_to_ist(dt):
    if not dt: return datetime.now(IST)
    if isinstance(dt, str):
        try: dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except: return datetime.now(IST)
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def process_public_incident(incident):
    incident_id = str(incident.get('_id'))
    lat = incident.get('lat') or incident.get('latitude', 0)
    lng = incident.get('lng') or incident.get('longitude', 0)
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
        'description': f"Emergency alert triggered by {user_name}.",
        'incident_type': incident_type,
        'severity': severity,
        'status': 'active',
        'latitude': float(lat),
        'longitude': float(lng),
        'address': address,
        'reported_by': user_name,
        'assigned_officer': incident.get('assigned_officer', 'Unassigned'),
        'created_at': created_at,
        'source': 'public'
    }

def process_police_incident(incident):
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

# Routes
@app.route('/')
@login_required
def dashboard():
    try:
        recent_police_incidents = list(incidents_police_collection.find().sort('created_at', -1).limit(5))
        recent_public_incidents = list(incidents_collection.find().sort('created_at', -1).limit(5))
        
        recent_incidents = []
        for incident in recent_police_incidents:
            incident_data = process_police_incident(incident)
            assignment = assigned_cases_collection.find_one({'incident_id': str(incident['_id'])})
            incident_data['is_assigned'] = assignment is not None
            recent_incidents.append(incident_data)
        
        for incident in recent_public_incidents:
            incident_data = process_public_incident(incident)
            assignment = assigned_cases_collection.find_one({'incident_id': str(incident['_id'])})
            incident_data['is_assigned'] = assignment is not None
            recent_incidents.append(incident_data)
        
        recent_incidents.sort(key=lambda x: x['created_at'], reverse=True)
        recent_incidents = recent_incidents[:5]
        
        total_police = incidents_police_collection.count_documents({})
        total_public = incidents_collection.count_documents({})
        total_incidents = total_police + total_public
        
        resolved_police = incidents_police_collection.count_documents({'status': 'resolved'})
        resolved_public = incidents_collection.count_documents({'status': 'resolved'})
        resolved_cases = db.resolved_cases.count_documents({})
        total_resolved = resolved_police + resolved_public + resolved_cases
        
        user_incidents = (incidents_police_collection.count_documents({'assigned_officer': current_user.username}) + 
                         incidents_collection.count_documents({'assigned_officer': current_user.username}))
        
        active_officers = police_officers_collection.count_documents({'status': 'active'})
        
        return render_template('dashboard.html', 
                             incidents=recent_incidents,
                             total_incidents=total_incidents,
                             resolved_incidents=total_resolved,
                             user_incidents=user_incidents,
                             active_officers=active_officers)
    except Exception as e:
        return render_template('dashboard.html', incidents=[], total_incidents=0, resolved_incidents=0, user_incidents=0, active_officers=0)

@app.route('/api/get-station-data')
def get_station_data():
    """API to get validation data for a specific station"""
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
        
        # Strict Validation using POLICE_DATABASE
        if police_station not in POLICE_DATABASE:
            flash('Invalid Police Station selected. Please select from the authentic list.', 'danger')
            return render_template('register.html', police_stations=STATION_NAMES)
            
        real_data = POLICE_DATABASE[police_station]
        
        if real_data['ward'] != ward_number:
            flash(f"Security Alert: Ward Number '{ward_number}' does not match official records for {police_station}. Expected: {real_data['ward']}", 'danger')
            return render_template('register.html', police_stations=STATION_NAMES)
            
        if real_data['reg_no'] != police_station_reg_no:
            flash(f"Security Alert: Registration Number '{police_station_reg_no}' does not match official records for {police_station}. Expected: {real_data['reg_no']}", 'danger')
            return render_template('register.html', police_stations=STATION_NAMES)

        if POLICE_users.find_one({'police_station_reg_no': police_station_reg_no}):
            flash('This Police Station is already registered.', 'danger')
            return render_template('register.html', police_stations=STATION_NAMES)
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html', police_stations=STATION_NAMES)
        
        try:
            base_username = re.sub(r'[^a-zA-Z0-9]', '', police_station).lower()[:15]
            reg_suffix = police_station_reg_no[-4:]
            username = f"{base_username}_{reg_suffix}"
            
            counter = 1
            original_username = username
            while POLICE_users.find_one({'username': username}):
                username = f"{original_username}_{counter}"
                counter += 1
            
            email = f"{username}@karnatakapolice.gov.in"
            
            new_user = {
                'username': username,
                'email': email,
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
            
            officer_data = {
                'user_id': res.inserted_id,
                'username': username,
                'email': email,
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
    police_incidents = list(incidents_police_collection.find().sort('created_at', -1))
    public_incidents = list(incidents_collection.find().sort('created_at', -1))
    
    all_incidents = []
    for i in police_incidents:
        d = process_police_incident(i)
        d['is_assigned'] = assigned_cases_collection.find_one({'incident_id': str(i['_id'])}) is not None
        all_incidents.append(d)
    for i in public_incidents:
        d = process_public_incident(i)
        d['is_assigned'] = assigned_cases_collection.find_one({'incident_id': str(i['_id'])}) is not None
        all_incidents.append(d)
    
    all_incidents.sort(key=lambda x: x['created_at'], reverse=True)
    
    stats = {
        'total': len(all_incidents),
        'police': sum(1 for i in all_incidents if i['source'] == 'police'),
        'public': sum(1 for i in all_incidents if i['source'] == 'public'),
        'high_severity': sum(1 for i in all_incidents if i['severity'] == 'high'),
        'active': sum(1 for i in all_incidents if i['status'] == 'active'),
        'resolved': sum(1 for i in all_incidents if i['status'] == 'resolved'),
        'assigned': sum(1 for i in all_incidents if i['is_assigned']),
        'unassigned': len(all_incidents) - sum(1 for i in all_incidents if i['is_assigned'])
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
    
    police = list(incidents_police_collection.find().limit(50))
    public = list(incidents_collection.find().limit(50))
    data = []
    for i in police:
        d = process_police_incident(i)
        d['is_assigned'] = assigned_cases_collection.find_one({'incident_id': str(i['_id'])}) is not None
        d['id'] = str(d['_id'])
        d['created_at'] = d['created_at'].isoformat()
        data.append(d)
    for i in public:
        d = process_public_incident(i)
        d['is_assigned'] = assigned_cases_collection.find_one({'incident_id': str(i['_id'])}) is not None
        d['id'] = str(d['_id'])
        d['created_at'] = d['created_at'].isoformat()
        data.append(d)
    return jsonify(data)

@app.route('/api/recent-activity')
@login_required
def recent_activity():
    activities = []
    recs = list(incidents_police_collection.find().sort('created_at', -1).limit(2))
    for r in recs:
        t = convert_to_ist(r.get('created_at'))
        activities.append({'text': f"New Police Incident: {r.get('title')}", 'time': t.strftime('%H:%M'), 'color': 'primary', 'icon': 'fa-exclamation-circle'})
    return jsonify({'activities': activities})

@app.route('/api/police-officers', methods=['GET', 'POST'])
@login_required
def police_officers_route():
    if request.method == 'POST':
        data = request.get_json()
        station = current_user.police_station
        
        uname = data.get('username')
        if not uname:
            uname = f"{data.get('full_name','').lower().replace(' ','.')}.{data.get('badge_number','')[-4:]}"
            
        if police_officers_collection.find_one({'$or': [{'badge_number': data.get('badge_number')}, {'username': uname}]}):
            return jsonify({'error': 'Exists'}), 400
            
        new_off = {
            'badge_number': data.get('badge_number'),
            'full_name': data.get('full_name'),
            'designation': data.get('designation'),
            'police_station': station,
            'email': data.get('email'),
            'username': uname,
            'phone': data.get('phone', ''),
            'status': 'active',
            'created_by': current_user.username,
            'created_at': datetime.now(IST)
        }
        res = police_officers_collection.insert_one(new_off)
        return jsonify({'message': 'Added', 'officer_id': str(res.inserted_id)})

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
    
    stats = {'total': total_police+total_public, 'active': active, 'resolved': resolved, 'high_severity': high}
    return render_template('reports.html', stats=stats, current_time=datetime.now(IST).strftime('%Y-%m-%d %H:%M'))

# Export Routes
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
        
        # --- POLICE INCIDENTS SECTION ---
        police_incidents = list(incidents_police_collection.find().sort('created_at', -1))
        if police_incidents:
            elements.append(Paragraph("POLICE INCIDENTS", styles['Heading2']))
            data = [['ID', 'Title', 'Severity', 'Status', 'Date']]
            for i in police_incidents:
                data.append([
                    i.get('incident_id', '')[:12],
                    i.get('title', '')[:50],  # Increased limit
                    i.get('severity', '').title(),
                    i.get('status', '').title(),
                    convert_to_ist(i.get('created_at')).strftime('%m/%d %H:%M')
                ])
            
            t = Table(data, colWidths=[1.1*inch, 3.0*inch, 0.7*inch, 0.7*inch, 1.1*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(t)
            elements.append(Spacer(1, 20))
            
        # --- PUBLIC INCIDENTS SECTION ---
        public_incidents = list(incidents_collection.find().sort('created_at', -1))
        if public_incidents:
            elements.append(Paragraph("PUBLIC INCIDENTS", styles['Heading2']))
            data = [['ID', 'Title', 'Severity', 'Status', 'Date']]
            for i in public_incidents:
                d = process_public_incident(i)
                data.append([
                    d['incident_id'][:12],
                    d['title'][:50],
                    d['severity'].title(),
                    d['status'].title(),
                    d['created_at'].strftime('%m/%d %H:%M')
                ])
            
            t = Table(data, colWidths=[1.1*inch, 3.0*inch, 0.7*inch, 0.7*inch, 1.1*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c757d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(t)
            elements.append(Spacer(1, 20))

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=swiftaid_report.pdf', 'Content-Type': 'application/pdf'})
    except Exception as e:
        print(f"PDF Error: {e}")
        flash(f"PDF Export error: {e}", "danger")
        return redirect(url_for('reports'))

@app.route('/reports/export/csv')
@login_required
def export_csv():
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Source', 'Incident ID', 'Title', 'Type', 'Severity', 'Status', 'Address', 'Reported By', 'Created At'])
        
        for i in incidents_police_collection.find():
            writer.writerow(['Police', i.get('incident_id'), i.get('title'), i.get('incident_type'), i.get('severity'), i.get('status'), i.get('address'), i.get('reported_by'), convert_to_ist(i.get('created_at')).strftime('%Y-%m-%d %H:%M:%S')])
            
        for i in incidents_collection.find():
            d = process_public_incident(i)
            writer.writerow(['Public', d['incident_id'], d['title'], d['incident_type'], d['severity'], d['status'], d['address'], d['reported_by'], d['created_at'].strftime('%Y-%m-%d %H:%M:%S')])
            
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
            writer.writerow(['Police', i.get('incident_id'), i.get('title'), i.get('incident_type'), i.get('severity'), i.get('status'), i.get('address'), i.get('reported_by'), convert_to_ist(i.get('created_at')).strftime('%Y-%m-%d %H:%M:%S')])
            
        for i in incidents_collection.find():
            d = process_public_incident(i)
            writer.writerow(['Public', d['incident_id'], d['title'], d['incident_type'], d['severity'], d['status'], d['address'], d['reported_by'], d['created_at'].strftime('%Y-%m-%d %H:%M:%S')])
            
        text_output.flush()
        csv_data = output.getvalue()
        text_output.close()
        output.close()
        
        return Response(csv_data, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=swiftaid_incidents_excel.csv"})
    except Exception as e:
        flash(f"Export error: {e}", "danger")
        return redirect(url_for('reports'))

if __name__ == '__main__':
    print("🚀 Starting SwiftAid Police Dashboard with Full Station Database...")
    app.run(debug=True)
##Korištene tehnologije
-2x XBee DigiMesh modula
-Python 3.12+
-Linux OS (Ubuntu)

##Konfiguracija Xbee-ja
-AP -> 1
-Isti network na oba modula -> 7FFF
-baudrate -> 9600
-znati njihove adrese (node1 -> 0013A20041F5B749  i node2 -> 0013A20041F5B771)

##Konfiguracija virtualnog environmenta
pip install digi-xbee

##Testiranje rada 
#1. Terminal
-cd /Direktorij
source .venv/bin/activate
-python3 node.py --port /dev/ttyUSB0 --baud 9600 --peer64 0013A20041F5B771 --mode listen na modulu B749

#2. Terminal
-cd /Direktorij
source .venv/bin/activate
python3 node.py --port /dev/ttyUSB1 --baud 9600 --peer64 0013A20041F5B749 --mode ping  na modulu B771


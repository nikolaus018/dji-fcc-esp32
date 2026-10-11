"""Single source of truth for the dji-fcc-esp32 hardware: parts, values and nets.

Both the schematic (gen_sch.py) and the board (gen_pcb.py) are generated from this file.

Pin keys in `pins` may be a pin number ("3"), a pin name ("GND", which maps every pin with that name)
or a "name#number" pair when a name is ambiguous. Pins not listed get a no-connect flag.
"""

R0603 = "Resistor_SMD:R_0603_1608Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
LED0603 = "LED_SMD:LED_0603_1608Metric"
SOT235 = "Package_TO_SOT_SMD:SOT-23-5"
SOT236 = "Package_TO_SOT_SMD:SOT-23-6"
TP = "TestPoint:TestPoint_Pad_D1.5mm"

# ref: dict(sym, fp, value, pins, note)
PARTS = {}


def part(ref, sym, fp, value, pins=None, **props):
    PARTS[ref] = dict(sym=sym, fp=fp, value=value, pins=pins or {}, props=props)


def passive(ref, sym, fp, value, a, b, **props):
    part(ref, sym, fp, value, {"1": a, "2": b}, **props)


def R(ref, value, a, b, **p):
    passive(ref, "Device:R", R0603, value, a, b, **p)


def C(ref, value, a, b, fp=C0603, **p):
    passive(ref, "Device:C", fp, value, a, b, **p)


# ----------------------------------------------------------------------------------------------
# MCU
# ----------------------------------------------------------------------------------------------
part("U1", "RF_Module:ESP32-S3-MINI-1", "RF_Module:ESP32-S2-MINI-1", "ESP32-S3-MINI-1-N8", {
    "GND": "GND", "3V3": "+3V3", "EN": "ESP_EN", "IO0": "IO0",
    "IO1": "J1_CC1", "IO2": "J1_CC2",
    "IO4": "VBAT_SENSE", "IO21": "VCHG_SENSE",
    "IO39": "CHRG", "IO38": "STDBY", "IO6": "BOOST_EN", "IO7": "LOAD_EN", "IO8": "LOAD_FAULT",
    "IO42": "LED_R", "IO41": "LED_G", "IO40": "LED_B",
    "USB_D-": "USB_DN", "USB_D+": "USB_DP",
    "TXD0": "UART_TX", "RXD0": "UART_RX",
}, mpn="ESP32-S3-MINI-1-N8")
R("R1", "10k", "ESP_EN", "+3V3")
C("C1", "1uF", "ESP_EN", "GND")
C("C2", "10uF", "+3V3", "GND", fp=C0805)
C("C3", "100nF", "+3V3", "GND")

# ----------------------------------------------------------------------------------------------
# 3V3 LDO (from the protected battery)
# ----------------------------------------------------------------------------------------------
part("U2", "Regulator_Linear:AP2112K-3.3", SOT235, "AP2112K-3.3",
     {"VIN": "VBAT", "EN": "VBAT", "GND": "GND", "VOUT": "+3V3"}, mpn="AP2112K-3.3TRG1")
C("C4", "10uF", "VBAT", "GND", fp=C0805)
C("C5", "10uF", "+3V3", "GND", fp=C0805)

# ----------------------------------------------------------------------------------------------
# Charger (J2 -> TP4056 -> battery) with DW01A + FS8205A protection in the battery negative leg
# ----------------------------------------------------------------------------------------------
part("J2", "Connector:USB_C_Receptacle_USB2.0_16P",
     "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "USB-C CHARGE", {
         "VBUS": "VBUS_CHG", "GND": "GND", "SHIELD": "GND", "CC1": "J2_CC1", "CC2": "J2_CC2",
         "D+": "USB2_DP_C", "D-": "USB2_DN_C",
     }, mpn="TYPE-C-31-M-12")
R("R2", "5.1k", "J2_CC1", "GND")
R("R3", "5.1k", "J2_CC2", "GND")
passive("D1", "Device:D_Zener", "Diode_SMD:D_SOD-123F", "SMF5.0A", "VBUS_CHG", "GND", mpn="SMF5.0A")
C("C6", "10uF", "VBUS_CHG", "GND", fp=C0805)

part("U3", "Battery_Management:TP4056-42-ESOP8", "Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.41x3.3mm",
     "TP4056", {"TEMP": "GND", "PROG": "PROG", "GND": "GND", "V_{CC}": "VBUS_CHG", "BAT": "VBAT",
                "~{STDBY}": "STDBY", "~{CHRG}": "CHRG", "CE": "VBUS_CHG", "EPAD": "GND"},
     mpn="TP4056-42-ESOP8")
R("R4", "4.7k", "PROG", "GND")  # 1200/4.7k = ~255 mA charge current
C("C7", "10uF", "VBAT", "GND", fp=C0805)
part("J3", "Connector_Generic:Conn_01x02", "Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal",
     "BATTERY 1S LiPo (+ on pin 1)", {"1": "VBAT", "2": "BNEG"}, mpn="S2B-PH-SM4-TB")
part("U4", "Battery_Management:DW01A", SOT236, "DW01A",
     {"OD": "DW_OD", "CS": "DW_CS", "OC": "DW_OC", "VCC": "DW_VCC", "GND": "BNEG"}, mpn="DW01A")
part("Q1", "dji_parts:FS8205A", "Package_SO:TSSOP-8_4.4x3mm_P0.65mm", "FS8205A",
     {"1": "DW_MID", "8": "DW_MID", "2": "BNEG", "3": "BNEG", "4": "DW_OD",
      "5": "DW_OC", "6": "GND", "7": "GND"}, mpn="FS8205A")
R("R7", "100", "VBAT", "DW_VCC")
C("C8", "100nF", "DW_VCC", "BNEG")
R("R8", "1k", "DW_CS", "GND")

# ----------------------------------------------------------------------------------------------
# Remote-side power: MT3608 boost -> TPS2553 current-limited switch -> J1 VBUS
# ----------------------------------------------------------------------------------------------
part("U5", "Regulator_Switching:MT3608", SOT236, "MT3608",
     {"SW": "VSW", "GND": "GND", "FB": "FB", "EN": "BOOST_EN", "IN": "VBAT"}, mpn="MT3608")
passive("L1", "Device:L", "Inductor_SMD:L_Sunlord_SWPA4020S", "4.7uH", "VBAT", "VSW", mpn="SWPA4020S4R7MT")
passive("D4", "Device:D_Schottky", "Diode_SMD:D_SMA", "SS34", "VBOOST", "VSW", mpn="SS34")  # K=1, A=2
C("C9", "22uF", "VBAT", "GND", fp=C0805)
C("C10", "22uF", "VBOOST", "GND", fp=C0805)
C("C11", "22uF", "VBOOST", "GND", fp=C0805)
R("R9", "220k", "VBOOST", "FB")   # Vout = 0.6 * (1 + 220k/30k) = 5.0 V
R("R10", "30k", "FB", "GND")
R("R11", "100k", "BOOST_EN", "GND")

part("U6", "dji_parts:TPS2553", SOT236, "TPS2553DBVR",
     {"IN": "VBOOST", "GND": "GND", "EN": "LOAD_EN", "FAULT": "LOAD_FAULT", "ILIM": "ILIM",
      "OUT": "VBUS_REM"}, mpn="TPS2553DBVR")
R("R12", "47k", "ILIM", "GND")   # ~540 mA current limit (25230/R[k]); datasheet: 520 mA @ 49.9k
R("R13", "100k", "LOAD_FAULT", "+3V3")
R("R14", "100k", "LOAD_EN", "GND")
C("C12", "100nF", "VBOOST", "GND")
C("C13", "10uF", "VBUS_REM", "GND", fp=C0805)

part("J1", "Connector:USB_C_Receptacle_USB2.0_16P",
     "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "USB-C REMOTE", {
         "VBUS": "VBUS_REM", "GND": "GND", "SHIELD": "GND", "CC1": "J1_CC1", "CC2": "J1_CC2",
         "D+": "USB_DP_C", "D-": "USB_DN_C",
     }, mpn="TYPE-C-31-M-12")
R("R15", "33k", "J1_CC1", "+3V3")   # Rp to 3V3: 36k +/-20% = default USB power (28.8..43.2k)
R("R16", "33k", "J1_CC2", "+3V3")
passive("D5", "Device:D_Zener", "Diode_SMD:D_SOD-123F", "SMF5.0A", "VBUS_REM", "GND", mpn="SMF5.0A")
part("U7", "Power_Protection:USBLC6-2SC6", SOT236, "USBLC6-2SC6",
     {"1": "USB_DP_C", "6": "USB_DP_J1", "3": "USB_DN_C", "4": "USB_DN_J1", "2": "GND", "5": "VBUS_REM"},
     mpn="USBLC6-2SC6")

# USB data path: the S3 has one USB PHY. J1 (remote) and J2 (computer, for flashing/updates) share it through a
# 2:1 switch whose select input is "J2 has VBUS". Plugged into a computer = ESP talks to J2, otherwise to J1.
part("U8", "Interface_USB:FSUSB42MUX", "Package_SO:MSOP-10_3x3mm_P0.5mm", "FSUSB42MUX",
     {"VCC": "+3V3", "GND": "GND", "SEL": "VCHG_SENSE", "~{OE}": "GND", "D+": "USB_DP", "D-": "USB_DN",
      "HSD1+": "USB_DP_J1", "HSD1-": "USB_DN_J1", "HSD2+": "USB2_DP", "HSD2-": "USB2_DN"}, mpn="FSUSB42MUX")
C("C15", "100nF", "+3V3", "GND")
part("U9", "Power_Protection:USBLC6-2SC6", SOT236, "USBLC6-2SC6",
     {"1": "USB2_DP_C", "6": "USB2_DP", "3": "USB2_DN_C", "4": "USB2_DN", "2": "GND", "5": "VBUS_CHG"},
     mpn="USBLC6-2SC6")

# ----------------------------------------------------------------------------------------------
# Status LED (R/G/B on the battery rail, sunk by GPIOs) and battery / charger sensing
# ----------------------------------------------------------------------------------------------
R("R17", "470", "VBAT", "LR_A")
passive("D6", "Device:LED", LED0603, "RED", "LED_R", "LR_A")
R("R18", "470", "VBAT", "LG_A")
passive("D7", "Device:LED", LED0603, "GREEN", "LED_G", "LG_A")
R("R19", "220", "VBAT", "LB_A")
passive("D8", "Device:LED", LED0603, "BLUE", "LED_B", "LB_A")
R("R20", "1M", "VBAT", "VBAT_SENSE")
R("R21", "1M", "VBAT_SENSE", "GND")
C("C14", "100nF", "VBAT_SENSE", "GND")
R("R22", "100k", "VBUS_CHG", "VCHG_SENSE")
R("R23", "150k", "VCHG_SENSE", "GND")

# ----------------------------------------------------------------------------------------------
# Test / programming pads (UART programming jig) and mechanical
# ----------------------------------------------------------------------------------------------
for ref, net in [("TP1", "ESP_EN"), ("TP2", "IO0"), ("TP3", "UART_TX"), ("TP4", "UART_RX"),
                 ("TP5", "+3V3"), ("TP6", "GND"), ("TP7", "VBAT"), ("TP8", "VBUS_REM")]:
    part(ref, "Connector:TestPoint", TP, net, {"1": net})
part("H1", "Mechanical:MountingHole", "MountingHole:MountingHole_2.2mm_M2", "M2")
part("H2", "Mechanical:MountingHole", "MountingHole:MountingHole_2.2mm_M2", "M2")
for i in (1, 2, 3):
    part(f"FID{i}", "Mechanical:Fiducial", "Fiducial:Fiducial_0.5mm_Mask1mm", "Fiducial")

# nets that need a PWR_FLAG (no power-output pin drives them)
PWR_FLAGS = ["GND", "VBUS_CHG", "VBOOST", "BNEG", "DW_VCC"]


# LCSC / JLCPCB part numbers (looked up on jlcpcb.com/partdetail/<C#>; see docs/BOM notes)
# Substituted 2026-10-11 because the first choices were out of stock at JLCPCB:
#   Q1: HXY MOSFET 8205A (TSSOP-8) instead of Fortune FS8205A (C14212)
#   D7/D8: the same Everlight 19-217 LEDs on the /6T reel instead of /3T (C72043, C72041)
LCSC_REF = {"U1": "C2913206", "U2": "C51118", "U3": "C16581", "U4": "C2927799", "Q1": "C5148694", "U5": "C84817",
            "U6": "C55266", "U7": "C7519", "U8": "C11355", "U9": "C7519", "J1": "C165948", "J2": "C165948", "J3": "C295747", "L1": "C48427",
            "D4": "C8678", "D1": "C707993", "D5": "C707993", "D6": "C2286",
            "D7": "C2986059", "D8": "C2986058"}
LCSC_R = {"10k": "C25804", "1k": "C21190", "100k": "C25803", "4.7k": "C23162", "100": "C22775", "470": "C23179",
          "220k": "C22961", "5.1k": "C23186", "30k": "C22984", "33k": "C4216", "47k": "C25819", "1M": "C22935",
          "150k": "C22807", "220": "C22962"}
LCSC_C = {("100nF", "0603"): "C14663", ("1uF", "0603"): "C15849", ("10uF", "0805"): "C15850", ("22uF", "0805"): "C45783"}

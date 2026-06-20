"""Humanización de codes crudos de PR (kits, armas, vehículos, mapas, gamemodes).

Los `.PRdemo` traen codes internos del juego (`mec_rifleman`, `rurif_ak74m_1p78`,
`ru_jep_tigr_pkp`, `albasrah_2`, `gpm_cq`). Este módulo es la **fuente única** de
nombres legibles en español: el scraper lo usa para generar
`graphs/demos/aliases.json`, que la web (fetch) y el bot (fetch) consumen.

Diccionarios curados a partir de investigación (PR wiki/manual, prstats, foros,
IMFDB). Las armas/vehículos se descomponen en prefijo(facción+tipo)+modelo+
accesorios para resolver el long tail sin caer en "Otro".
"""

from __future__ import annotations

import re
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Gamemodes (set fijo)
# ─────────────────────────────────────────────────────────────────────────────
GAMEMODES = {
    "gpm_cq": "AAS",
    "gpm_insurgency": "Insurgencia",
    "gpm_skirmish": "Skirmish",
    "gpm_vehicles": "Vehicle Warfare",
    "gpm_gungame": "Gun Game",
    "gpm_cnc": "Comando (CNC)",
    "gpm_coop": "Co-op",
    "": "—",
}

# ─────────────────────────────────────────────────────────────────────────────
# Mapas (87 curados)
# ─────────────────────────────────────────────────────────────────────────────
MAPS = {
    "test_airfield": "Test Airfield", "deagle5": "Deagle", "gaza_2": "Gaza",
    "khamisiyah": "Khamisiyah", "asad_khal": "Asad Khal", "shipment": "Shipment",
    "albasrah_2": "Al Basrah", "kokan": "Kokan", "fallujah_west": "Fallujah West",
    "black_gold": "Black Gold", "the_falklands": "The Falklands", "beirut": "Beirut",
    "donbas": "Donbas", "muttrah_city_2": "Muttrah City",
    "road_to_damascus": "Road to Damascus", "sbeneh_outskirts": "Sbeneh Outskirts",
    "kashan_desert": "Kashan Desert", "wanda_shan": "Wanda Shan",
    "assault_on_grozny": "Assault on Grozny", "silent_eagle": "Silent Eagle",
    "operation_marlin": "Operation Marlin", "operation_falcon": "Operation Falcon",
    "burning_sands": "Burning Sands", "icebreaker": "Icebreaker", "saaremaa": "Saaremaa",
    "kafar_halab": "Kafr Halab", "adak": "Adak",
    "operation_soul_rebel": "Operation Soul Rebel", "talbisah": "Talbisah",
    "yamalia": "Yamalia", "grostok": "Grostok", "dovre": "Dovre",
    "korbach_offensive": "Korbach Offensive", "shijiavalley": "Shijia Valley",
    "zakho": "Zakho", "goose_green": "Goose Green", "pavlovsk_bay": "Pavlovsk Bay",
    "vung_ro": "Vung Ro", "operation_thunder": "Operation Thunder",
    "shahadah": "Shahadah", "test_bootcamp": "Test Bootcamp",
    "krivaja_valley": "Krivaja Valley", "carentan": "Carentan",
    "ascheberg": "Ascheberg", "omaha_beach": "Omaha Beach", "dragon_fly": "Dragon Fly",
    "ramiel": "Ramiel", "op_barracuda": "Operation Barracuda", "route": "Route E-106",
    "xiangshan": "Xiangshan", "fields_of_kassel": "Fields of Kassel",
    "stalingrad": "Stalingrad", "masirah": "Masirah", "hill_488": "Hill 488",
    "outpost": "Outpost", "ras_el_masri_2": "Ras El Masri", "ulyanovsk": "Ulyanovsk",
    "vadso_city": "Vadso City", "bamyan": "Bamyan", "nuijamaa": "Nuijamaa",
    "stalingrad_summer": "Stalingrad Summer", "battle_of_debrecen": "Battle of Debrecen",
    "dovre_winter": "Dovre Winter", "musa_qala": "Musa Qala",
    "operation_bobcat": "Operation Bobcat", "assault_on_mestia": "Assault on Mestia",
    "iron_ridge": "Iron Ridge", "sahel": "Sahel", "merville": "Merville",
    "hades_peak": "Hades Peak", "reichswald": "Reichswald", "korengal": "Korengal Valley",
    "operation_brunswick": "Operation Brunswick", "kozelsk": "Kozelsk",
    "brecourt_assault": "Brecourt Assault", "fools_road": "Fools Road",
    "kunar_province": "Kunar Province", "andromeda": "Andromeda",
    "battle_of_kerch": "Battle of Kerch", "rzhev": "Rzhev",
    "charlies_point": "Charlie's Point", "lashkar_valley": "Lashkar Valley",
    "battle_of_ia_drang": "Battle of Ia Drang", "tad_sae": "Tad Sae Offensive",
    "belyaevo": "Belyaevo", "karbala": "Karbala",
}

# ─────────────────────────────────────────────────────────────────────────────
# Kits: facción + rol
# ─────────────────────────────────────────────────────────────────────────────
KIT_FACTIONS = {
    "us": "EE.UU.", "usa": "EE.UU.", "ru": "Rusia", "mec": "MEC", "fr": "Francia",
    "pl": "Polonia", "gb": "Reino Unido", "ger": "Alemania", "idf": "Israel (FDI)",
    "nl": "Países Bajos", "ch": "China", "cf": "Canadá", "saf": "Sudáfrica",
    "arf": "Fuerzas Africanas", "fsa": "Ejército Sirio Libre", "taliban": "Talibán",
    "hamas": "Hamás", "chinsurgent": "Insurgentes (China)",
    "meinsurgent": "Insurgentes (Oriente Medio)", "ru90": "Rusia (años 90)",
    "chechen90": "Chechenia (años 90)", "chinsurgent90": "Insurgentes China (años 90)",
    "arg82": "Argentina (1982)", "gb82": "Reino Unido (1982)",
    "vnnva": "Vietnam del Norte", "vnusmc": "USMC (Vietnam)", "vnusa": "EE.UU. (Vietnam)",
    "ww2usa": "EE.UU. (WWII)", "ww2ger": "Alemania (WWII)", "ww2ger41": "Alemania (WWII, 1941)",
    "ww2rus": "URSS (WWII)", "ww2rusearly": "URSS (WWII, temprana)",
    "chmoon": "China (Luna)", "plmoon": "Polonia (Luna)", "gungame": "Gun Game",
    "global": "Global",
}

KIT_ROLES = {
    "combat_engineer": "Ingeniero de combate", "automatic_rifle": "Fusilero automático",
    "machine_gun": "Ametrallador", "rifleman_ap": "Fusilero AP", "riflemanap": "Fusilero AP",
    "riflemanat": "Fusilero AT", "anti-tank": "Anti-tanque", "rifleman": "Fusilero",
    "marksman": "Tirador designado", "specialist": "Especialista",
    "specop": "Fuerzas Especiales", "spotter": "Observador", "sniper": "Francotirador",
    "grenadier": "Granadero", "breacher": "Asaltante de brechas",
    "crewman": "Tripulante de vehículo", "tanker": "Tripulante de vehículo",
    "engineer": "Ingeniero", "sapper": "Zapador", "recon": "Reconocimiento",
    "officer": "Oficial", "pilot": "Piloto", "support": "Apoyo", "assault": "Asalto",
    "medic": "Médico", "unarmed": "Desarmado", "para": "Paracaidista",
    "makarov": "Pistola Makarov", "shotgun": "Escopeta", "pistol": "Pistola",
    "pickup": "Equipo recogido", "impact": "Granada de impacto", "grenade": "Granadero",
    "knife": "Cuchillo", "m79": "Lanzagranadas M79", "dmr": "Tirador designado",
    "smg": "Subfusil", "auto": "Fusilero automático", "bolt": "Fusil de cerrojo",
    "semi": "Fusil semiautomático", "insurgent": "Insurgente", "hat": "Anti-tanque pesado",
    "lat": "Anti-tanque ligero", "at": "Anti-tanque", "aa": "Antiaéreo",
    "mg": "Ametrallador", "gl": "Lanzagranadas", "rifle": "Fusil", "rif": "Fusil",
}
# Match longest role key first (so riflemanat beats rifleman beats rifle, etc.)
_ROLE_KEYS = sorted(KIT_ROLES, key=len, reverse=True)
_KIT_VARIANT_SUFFIX = re.compile(
    r'_(?:alt\d*|night|iron|scope|old|ziptie|reddot|wood|q\d+|idx\d+|\d+)$', re.I)

# ─────────────────────────────────────────────────────────────────────────────
# Armas: prefijo(facción+tipo) + modelo + accesorios
# ─────────────────────────────────────────────────────────────────────────────
WEAPON_PREFIXES = {
    "rurif": ("Rusia", "rifle"), "rulmg": ("Rusia", "LMG"), "rummg": ("Rusia", "MMG"),
    "rushmg": ("Rusia", "HMG"), "rusni": ("Rusia", "sniper"), "rupis": ("Rusia", "pistol"),
    "rusht": ("Rusia", "shotgun"), "ruhgr": ("Rusia", "grenade"), "rushgr": ("Rusia", "grenade"),
    "rurgl": ("Rusia", "grenade_launcher"), "rulat": ("Rusia", "AT"), "rukni": ("Rusia", "knife"),
    "rumin": ("Rusia", "explosive"),
    "usrif": ("EE.UU.", "rifle"), "uslmg": ("EE.UU.", "LMG"), "usmmg": ("EE.UU.", "MMG"),
    "ushmg": ("EE.UU.", "HMG"), "ussni": ("EE.UU.", "sniper"), "uspis": ("EE.UU.", "pistol"),
    "ussht": ("EE.UU.", "shotgun"), "ushgr": ("EE.UU.", "grenade"), "usrgl": ("EE.UU.", "grenade_launcher"),
    "uslat": ("EE.UU.", "AT"), "usat": ("EE.UU.", "AT"), "usatp": ("EE.UU.", "AT"),
    "usaa": ("EE.UU.", "AA"), "usaas": ("EE.UU.", "AA"), "uskni": ("EE.UU.", "knife"),
    "usmin": ("EE.UU.", "explosive"), "usagl": ("EE.UU.", "grenade_launcher"),
    "mecrif": ("MEC", "rifle"), "meclmg": ("MEC", "LMG"), "mecmmg": ("MEC", "MMG"),
    "mecsni": ("MEC", "sniper"), "mecgl": ("MEC", "grenade_launcher"), "meclat": ("MEC", "AT"),
    "meckni": ("MEC", "knife"),
    "gerrif": ("Alemania", "rifle"), "gerlmg": ("Alemania", "LMG"), "germmg": ("Alemania", "MMG"),
    "gersni": ("Alemania", "sniper"), "gerpis": ("Alemania", "pistol"), "gerhgr": ("Alemania", "grenade"),
    "gergl": ("Alemania", "grenade_launcher"), "gerlat": ("Alemania", "AT"), "gerat": ("Alemania", "AT"),
    "gerkni": ("Alemania", "knife"), "germin": ("Alemania", "explosive"),
    "chrif": ("China", "rifle"), "chlmg": ("China", "LMG"), "chmmg": ("China", "MMG"),
    "chhmg": ("China", "HMG"), "chsht": ("China", "shotgun"), "chhgr": ("China", "grenade"),
    "chrgl": ("China", "grenade_launcher"), "chlat": ("China", "AT"), "chat": ("China", "AT"),
    "chaa": ("China", "AA"), "chpis": ("China", "pistol"), "chkni": ("China", "knife"),
    "chmin": ("China", "explosive"), "chmoonpis": ("China", "pistol"),
    "insrg": ("Insurgentes", "rifle"), "insrgl": ("Insurgentes", "grenade_launcher"),
    "insmmg": ("Insurgentes", "MMG"), "insrglmg": ("Insurgentes", "MMG"),
    "inslat": ("Insurgentes", "AT"), "insgr": ("Insurgentes", "grenade"), "inskni": ("Insurgentes", "knife"),
    "idfrif": ("Israel", "rifle"), "idflmg": ("Israel", "LMG"), "idfmmg": ("Israel", "MMG"),
    "idfsni": ("Israel", "sniper"), "idfhgr": ("Israel", "grenade"),
    "idfrgl": ("Israel", "grenade_launcher"), "idflat": ("Israel", "AT"),
    "idfat": ("Israel", "AT"), "idfpis": ("Israel", "pistol"), "idfkni": ("Israel", "knife"),
    "plrif": ("Polonia", "rifle"), "plmmg": ("Polonia", "MMG"), "plmg": ("Polonia", "LMG"),
    "plsni": ("Polonia", "sniper"), "plhgr": ("Polonia", "grenade"), "plrgl": ("Polonia", "grenade_launcher"),
    "pllat": ("Polonia", "AT"), "plat": ("Polonia", "AT"), "plaa": ("Polonia", "AA"),
    "plpis": ("Polonia", "pistol"), "plkni": ("Polonia", "knife"), "plmoonpis": ("Polonia", "pistol"),
    "cfrif": ("Canadá", "rifle"), "cflmg": ("Canadá", "LMG"), "cfmmg": ("Canadá", "MMG"),
    "cfsni": ("Canadá", "sniper"), "cfhgr": ("Canadá", "grenade"), "cfrgl": ("Canadá", "grenade_launcher"),
    "cflat": ("Canadá", "AT"),
    "frrif": ("Francia", "rifle"), "frlmg": ("Francia", "LMG"), "frsni": ("Francia", "sniper"),
    "frsht": ("Francia", "shotgun"), "frhgr": ("Francia", "grenade"), "frrgl": ("Francia", "grenade_launcher"),
    "frlat": ("Francia", "AT"), "frpis": ("Francia", "pistol"), "frkni": ("Francia", "knife"),
    "frcmg": ("Francia", "MMG"),
    "nlrif": ("Países Bajos", "rifle"), "nllmg": ("Países Bajos", "LMG"), "nlmmg": ("Países Bajos", "MMG"),
    "nlsni": ("Países Bajos", "sniper"), "nlhgr": ("Países Bajos", "grenade"),
    "nlrgl": ("Países Bajos", "grenade_launcher"),
    "gbrif": ("Reino Unido", "rifle"), "gblmg": ("Reino Unido", "LMG"), "gbmmg": ("Reino Unido", "MMG"),
    "gbsni": ("Reino Unido", "sniper"), "gbsht": ("Reino Unido", "shotgun"), "gbhgr": ("Reino Unido", "grenade"),
    "gbrgl": ("Reino Unido", "grenade_launcher"), "gblat": ("Reino Unido", "AT"), "gbat": ("Reino Unido", "AT"),
    "gbaa": ("Reino Unido", "AA"), "gbpis": ("Reino Unido", "pistol"), "gbkni": ("Reino Unido", "knife"),
    "gbgmg": ("Reino Unido", "grenade_launcher"),
    "argrif": ("Argentina", "rifle"), "arglmg": ("Argentina", "LMG"), "argkni": ("Argentina", "knife"),
    "argmin": ("Argentina", "explosive"),
    "vnrif": ("Vietnam (NVA)", "rifle"), "vnlmg": ("Vietnam (NVA)", "LMG"), "vnmmg": ("Vietnam (NVA)", "MMG"),
    "vnpis": ("Vietnam (NVA)", "pistol"), "vnhgr": ("Vietnam (NVA)", "grenade"), "vnat": ("Vietnam (NVA)", "AT"),
    "rorif": ("Rumania", "rifle"), "iraqaa": ("Irak", "AA"), "safat": ("Insurgentes (SAF)", "AT"),
}

WEAPON_MODELS = {
    # Rusia
    "ak74m": "AK-74M", "ak74": "AK-74", "ak74s": "AK-74 (plegable)", "ak47": "AK-47",
    "akms": "AKMS", "aks_74u": "AKS-74U", "aks74": "AKS-74", "svd": "SVD Dragunov",
    "mosin_m9130": "Mosin-Nagant M91/30", "m9130": "Mosin-Nagant M91/30", "svt40": "SVT-40",
    "ppd40": "PPD-40", "ptrs41": "PTRS-41", "sv98": "SV-98", "rpk74m": "RPK-74M",
    "rpk74": "RPK-74", "rpk": "RPK", "pkm": "PKM", "pkp": "PKP Pecheneg",
    "makarov": "Makarov PM", "tt33": "Tokarev TT-33", "saiga12": "Saiga-12",
    "rgo": "RGO", "rgd5": "RGD-5", "rgd33": "RGD-33", "rkg3": "RKG-3", "rpg43": "RPG-43",
    "rpg7": "RPG-7", "rpg7v2": "RPG-7V2", "rpg26": "RPG-26", "rpg29": "RPG-29",
    "mon50": "MON-50", "tm62m": "TM-62M", "pomz": "POMZ", "tm35": "TM-35",
    "dshk": "DShK", "kord": "Kord", "nsvt": "NSVT",
    # EE.UU.
    "m4": "M4A1", "m4scope": "M4A1", "m16a4": "M16A4", "m16a1": "M16A1", "m16a2": "M16A2",
    "m14": "M14", "m14ebr": "M14 EBR", "mk12spr": "Mk 12 SPR", "m1garand": "M1 Garand",
    "m1carbine": "M1 Carbine", "mp5": "H&K MP5A3", "thompson": "M1928 Thompson",
    "greasegun": "M3 Grease Gun", "m249": "M249 SAW", "m240g": "M240G", "m240b": "M240B",
    "m60": "M60", "m1919a6": "M1919A6", "m1918": "M1918 BAR", "m2hb": "M2HB .50",
    "m1014": "Benelli M1014", "remington870": "Remington 870", "mossberg590": "Mossberg 590",
    "trenchgun": "M1897 Trench Gun", "m40a3": "M40A3", "m24": "M24 SWS",
    "92fs": "Beretta 92FS", "p226": "SIG P226", "colt1911": "Colt M1911",
    "m67": "Granada M67", "mk2": "Granada Mk 2", "m61": "Granada M61",
    "at4": "M136 AT4", "smaw": "Mk 153 SMAW", "m72": "M72 LAW", "m20": "M20 Super Bazooka",
    "m1bazooka": "M1 Bazooka", "predator": "FGM-148 Javelin", "fm92a": "FIM-92 Stinger",
    "claymore": "M18 Claymore", "m2a3": "Mina M2A3", "m1a1": "Mina M1A1",
    # MEC / G3
    "g3": "H&K G3", "g3sg1": "H&K G3SG/1", "g3sg14x": "H&K G3SG/1 (4x)",
    "g3zpoint": "H&K G3 (Z-Point)", "ssgp1": "Steyr SSG-P1",
    # Alemania
    "g36": "H&K G36", "g36k": "H&K G36K", "g43": "Gewehr 43", "k98": "Karabiner 98k",
    "k98zf39": "Karabiner 98k (ZF39)", "k98sb": "Karabiner 98k (bayoneta)", "stg44": "StG 44",
    "mp40": "MP40", "mp7": "H&K MP7", "g22": "G22 (AWM)", "mg34": "MG34", "mg42": "MG42",
    "mg3": "MG3", "mg4": "H&K MG4", "fg42": "FG42", "p8": "H&K USP (P8)", "p38": "Walther P38",
    "hk417": "H&K HK417", "m26": "Granada M26", "dm51": "Granada DM51",
    "pzf3": "Panzerfaust 3", "pzf60": "Panzerfaust 60", "pzf100": "Panzerfaust 100",
    "panzerschreck": "Panzerschreck", "km2000": "Eickhorn KM2000", "smine": "S-Mine",
    # China
    "qbz95": "QBZ-95", "qbz95b": "QBZ-95B", "qbu88": "QBU-88", "qbb95": "QBB-95",
    "type56": "Type 56", "type82": "Granada Type 82", "type85": "Type 85", "type66": "Mina Type 66",
    "qsz92": "QSZ-92", "norinco982": "Norinco 982", "qw2": "QW-2", "pf89": "PF-89", "pf98": "PF-98",
    # Insurgentes
    "akm": "AKM", "akmgl": "AKM (GP-25)", "svdwood": "SVD (madera)", "simonov": "SKS Simonov",
    "ppsh41": "PPSh-41", "m79": "M79", "fnfal": "FN FAL", "fnfalblack": "FN FAL",
    "scorpion": "Škorpion vz.61", "browninghipower": "Browning Hi-Power", "sa7": "Strela-2 (SA-7)",
    "ak74gl": "AK-74 (GP-25)",
    # Israel
    "mtar21": "MTAR-21 (X95)", "tar21": "TAR-21", "tar21c": "CTAR-21", "tar21s": "STAR-21",
    "tar21rf": "TAR-21", "menusar": "Menusar", "mekotzar": "Mekotzrar", "mekotzrar": "Mekotzrar",
    "galilsar": "Galil SAR", "negev": "IWI Negev", "fnmag": "FN MAG", "jericho941": "IWI Jericho 941",
    "m26a2": "Granada M26A2", "matador": "MATADOR", "m72a7": "M72A7 LAW",
    # Polonia
    "beryl": "FB Beryl wz.96", "beryl_mini": "FB Mini-Beryl", "ukm2000": "UKM-2000",
    "alex": "Bor/Alex", "trg22": "Sako TRG-22", "rgo88": "Granada RGO-88", "spike": "Spike",
    "wist94": "WIST-94", "grom": "Grom", "wz92": "Cuchillo WZ-92", "rpg7w2": "RPG-7W2",
    # Canadá
    "c7": "Colt Canada C7A2", "c8a3": "Colt Canada C8A3", "ar10t": "AR-10(T)", "c9": "C9A2",
    "c6": "C6 GPMG", "c14": "C14 Timberwolf", "c13": "Granada C13",
    # Francia
    "famas": "FAMAS F1", "minimi": "FN Minimi", "frf2": "FR-F2", "of37": "Granada OF37",
    "pamasg1": "PAMAS G1", "abl": "LRAC F1", "anf1": "AA-52 (ANF1)",
    # Países Bajos
    "c7nld": "Colt Canada C7NLD", "c8nld": "Colt Canada C8NLD", "nr300": "Granada NR300", "awm": "AWM",
    # Reino Unido
    "l85a2": "SA80 L85A2", "l86": "L86 LSW", "l1a1": "L1A1 SLR", "l128a1": "L128A1",
    "l115a3": "L115A3 AWM", "l42a1": "L42A1", "enfieldno4": "Lee-Enfield No.4",
    "enfieldno1mk3": "Lee-Enfield No.1 Mk III", "sterling": "Sterling", "gpmg": "L7A2 GPMG",
    "l4bren": "L4 Bren", "l109": "Granada L109", "l2a2": "Granada L2A2", "l2a1": "Carl Gustaf L2A1",
    "nlaw": "NLAW", "law66": "M72 LAW", "blowpipe": "Blowpipe", "glock17": "Glock 17",
    "l9": "Browning Hi-Power (L9)", "l134a1": "L134A1 GMG", "l22a2": "L22A2",
    # Argentina
    "fmfal": "FM FAL", "fmparafal": "FM Para-FAL", "fmfap": "FM FAP", "ml63": "Halcón ML-63",
    "fmk1": "Mina FMK-1", "fmk3": "FMK-3",
    # Vietnam
    "nagant": "Mosin-Nagant M44", "nagantzf": "Mosin-Nagant (PU)", "dp27": "DP-27",
    "mat49": "MAT-49", "betty": "Bouncing Betty", "type36": "Type 36 (RPG-2)",
    # Rumania / misc
    "md63": "PM md.63", "eryx": "ERYX", "stinger": "FIM-92 Stinger",
    "f1grenade": "Granada F1", "f1": "Granada F1",
}

WEAPON_ATTACHMENTS = {
    "1p78": "1P78", "acog": "ACOG", "elcan": "ELCAN", "eotech": "EOTech", "aimpoint": "Aimpoint",
    "kobra": "Kobra", "mepro": "Meprolight", "mars": "MARS", "zpoint": "Z-Point", "susat": "SUSAT",
    "pgo": "PGO-7", "gbpo40": "GBPO-40", "pu": "PU", "reddot": "punto rojo",
    "scope": "mira", "iron": "hierro", "deployed": "bípode", "dmr": "DMR", "sg1": "SG/1",
    "sup": "silenciador", "noris": "sin mira", "tracer": "trazadora", "frag": "fragmentación",
    "smoke": "humo", "buck": "perdigones", "slug": "bala", "tandem": "tándem",
    "ugl": "lanzagranadas", "gl": "lanzagranadas", "ag36": "AG36", "wood": "madera",
    "wooden": "madera", "fgrip": "empuñadura", "mini": "compacto", "obrez": "recortado",
    "caged": "jaula", "bayonet": "bayoneta", "4x": "4x", "3x": "3x", "alt": "alt.",
}

WEAPON_SPECIAL = {
    "?": ("Entorno / Desconocido", "unknown"),
}
# Clases/prefijos de arma montada en vehículo o emplazada (al inicio del code).
_VEHICLE_WEAPON_PREFIXES = (
    "apc_", "ifv_", "ahe_", "the_", "tnk_", "jet_", "aav", "aav_", "sam_", "aas_",
    "ats_", "atm_", "hmg_", "gmg_", "agl_", "50cal_", "deployable_", "stationary_",
    "technical_", "dumpster_", "static_", "igla_", "zu23", "zpu", "pak", "flak",
    "uralzu", "boat_", "us_agl", "us_aav", "ru_aav", "wasp_",
)
# Substrings que delatan arma de vehículo/emplazada en cualquier posición.
_VEHICLE_WEAPON_HINTS = (
    "coax", "_tnk_", "_jet_", "_ahe_", "_apc_", "_ifv_", "_aav", "_shp_", "barrel",
    "maingun", "primarygun", "minigun", "cannon", "mortar", "artillery", "rocket_pod",
    "rocketpod", "missile_launcher", "missle_launcher", "_gun_", "towlauncher",
)
# Emplazamientos estáticos / desplegables (NO son vehículos tripulados móviles):
# torretas, morteros, ATGM fijos, AA estático, artillería. Se separan de los
# vehículos para el desglose de "kills con vehículos".
_EMPLACEMENT_WEAPON_PREFIXES = (
    "deployable_", "static_", "stationary_", "artillery_", "mortar_", "50cal_",
    "hmg_", "gmg_", "agl_", "igla_", "sam_", "ats_", "aas_", "wasp_", "uralzu",
    "zu23", "zpu", "pak", "flak", "aa_", "aaa_", "usaa", "dumpster_",
)
# Clases de vehículo que en realidad son emplazamientos estáticos.
_EMPLACEMENT_CLASSES = {"ats", "aas"}
# Tokens de cola (parte del arma) a descartar al inferir el modelo del vehículo.
_VEHICLE_WEAPON_TAIL = {
    "coax", "barrel", "gun", "guns", "maingun", "primarygun", "secondarygun",
    "barrelgun", "hei", "he", "heat", "frag", "airburst", "launcher", "cannon",
    "rocket", "rockets", "pod", "missile", "missle", "sa19launcher", "amraamlauncher",
    "hydralauncher", "stinger", "g", "r", "nobox", "mounted", "tripod", "turret",
    "barrelhei", "barrelheat", "gunbarrelheat", "gunbarrelhei", "sec", "alt", "ww2",
}
# Categoría amplia (para el desglose -assets) según el "kind" de VEHICLE_CLASSES.
_VTYPE_BY_CLASS_KIND = {
    "truck": "ground", "jeep": "ground", "apc": "ground", "ifv": "ground",
    "tank": "ground", "aa": "ground", "atgm": "ground", "bike": "ground",
    "transport_heli": "air", "attack_heli": "air", "jet": "air", "plane": "air",
    "boat": "naval", "ship": "naval", "carrier": "naval",
}
# Codes legacy en CamelCase sin prefijo de clase (token0 = vehículo).
_LEGACY_VEHICLE_WEAPON = {
    "leopard2": "Leopard 2A6", "leopard": "Leopard 2A6", "panzer": "Panzer IV",
    "btr": "BTR-80", "brdm": "BRDM-2", "abrams": "M1A1 Abrams", "m4": "M4A3 Sherman",
    "sherman": "M4A3 Sherman", "dt27": "T-34", "sdkfz231": "Sd.Kfz. 231",
}
# Armas cuerpo a cuerpo y explosivos colocables (no llevan prefijo de facción+tipo).
_MELEE_EXPLOSIVE = {
    "kni": ("knife", "Cuchillo"), "c4": ("explosive", "C4"), "at_mine": ("explosive", "Mina AT"),
    "ied": ("explosive", "IED"), "satchel": ("explosive", "Carga explosiva"),
    "tnt": ("explosive", "TNT"), "dynamite": ("explosive", "Dinamita"),
    "ziptie": ("knife", "Brida (captura)"),
}

# ─────────────────────────────────────────────────────────────────────────────
# Vehículos: facción + clase + modelo
# ─────────────────────────────────────────────────────────────────────────────
VEHICLE_FACTIONS = {
    "us": "EE.UU.", "ru": "Rusia", "mec": "MEC", "ch": "China", "idf": "Israel",
    "gb": "Reino Unido", "gb82": "Reino Unido (1982)", "ger": "Alemania", "fr": "Francia",
    "nl": "Países Bajos", "pl": "Polonia", "cf": "Canadá", "saf": "Siria",
    "fsa": "Ejército Libre Sirio", "arf": "Combatientes Africanos", "nva": "Vietnam del Norte",
    "vc": "Vietcong", "arg": "Argentina", "mil": "Milicia", "civ": "Civil",
}
VEHICLE_CLASSES = {
    "trk": ("Camión", "truck"), "jep": ("Jeep", "jeep"), "the": ("Heli. transporte", "transport_heli"),
    "ahe": ("Heli. ataque", "attack_heli"), "apc": ("APC", "apc"), "ifv": ("IFV", "ifv"),
    "tnk": ("Tanque", "tank"), "jet": ("Jet", "jet"), "aav": ("Antiaéreo", "aa"),
    "atm": ("ATGM (vehículo)", "atgm"), "atc": ("Control aéreo", "carrier"),
    "ats": ("ATGM (estático)", "atgm"), "boat": ("Bote", "boat"), "shp": ("Embarcación", "ship"),
    "air": ("Avión", "plane"), "bik": ("Moto", "bike"), "carrier": ("Portaaviones", "carrier"),
}
# Modelos: clave = porción tras facción+clase (o code completo para estáticos).
VEHICLE_MODELS = {
    "support": "Camión de apoyo", "logistics": "Camión de logística",
    "kamaz_support": "KamAZ (apoyo)", "kamaz_logistics": "KamAZ (logística)",
    "hmmwv": "HMMWV", "hmmwv_support": "HMMWV (apoyo)", "hmmwv_uparmored": "HMMWV (blindado)",
    "hmmwv_crows": "HMMWV (CROWS)", "tigr": "GAZ Tigr", "tigr_pkp": "GAZ Tigr (PKP)",
    "uaz": "UAZ-469", "uaz_mg": "UAZ-469 (MG)", "brdm2": "BRDM-2", "gwagon": "Mercedes G-Wagon",
    "kubel": "Kübelwagen", "landrover": "Land Rover", "fennek": "Fennek", "bushmaster": "Bushmaster",
    "mengshi": "Dongfeng Mengshi", "m151a2": "M151A2", "willysmb": "Willys MB",
    "technical": "Technical", "technical_rocket": "Technical (cohetes)", "car": "Coche civil",
    "car_bomber": "Coche bomba", "forklift": "Montacargas",
    "uh1n": "UH-1N Twin Huey", "uh1d": "UH-1D Huey", "uh1h": "UH-1H Huey",
    "uh60": "UH-60 Black Hawk", "chinook": "CH-47 Chinook", "mi8": "Mi-8 Hip",
    "mi8amtsh": "Mi-8AMTSh Hip", "mi17": "Mi-17 Hip", "nh90": "NH90", "merlin": "AW101 Merlin",
    "gazelle": "SA341 Gazelle", "z8": "Z-8", "z9b": "Z-9B", "mv22": "MV-22 Osprey",
    "mh6": "MH-6 Little Bird", "lynx": "Westland Lynx", "ch146": "CH-146 Griffon",
    "ah1z": "AH-1Z Viper", "ah6": "AH-6 Little Bird", "apache": "AH-64 Apache",
    "kiowa": "OH-58 Kiowa", "mi24": "Mi-24 Hind", "havoc": "Mi-28 Havoc", "z10": "Z-10",
    "sokol": "PZL W-3 Sokół", "ec635": "EC635", "tiger": "Eurocopter Tiger",
    "aavp7a1": "AAVP7A1", "lav25": "LAV-25", "lav3": "LAV III", "stryker": "M1126 Stryker",
    "m113": "M113", "btr80": "BTR-80", "btr80a": "BTR-80A", "btr82am": "BTR-82AM",
    "namer": "Namer", "warrior": "FV510 Warrior", "cv90": "CV9035", "vab": "VAB", "vbci": "VBCI",
    "rosomak": "KTO Rosomak", "fuchs": "TPz Fuchs", "mtlb": "MT-LB", "wz551": "WZ-551",
    "zbl08": "ZBL-08", "boxer": "GTK Boxer", "lvtp7": "LVTP-7", "ypr50": "YPR-765",
    "m2a2": "M2A2 Bradley", "bmp1": "BMP-1", "bmp2": "BMP-2", "bmp2m": "BMP-2M", "bmp3": "BMP-3",
    "scimitar": "FV107 Scimitar", "scorpion": "FV101 Scorpion", "coyote": "Coyote", "puma": "SPz Puma",
    "m8": "M8 Greyhound", "saladin": "Alvis Saladin",
    "m1a2": "M1A2 Abrams", "m1a1": "M1A1 Abrams", "t72": "T-72", "t72s": "T-72S", "t72b": "T-72B",
    "t72av": "T-72AV", "t72m1": "T-72M1", "t90": "T-90", "t62": "T-62", "t55": "T-55",
    "t34": "T-34", "t34_85": "T-34-85", "pt76": "PT-76", "pt91": "PT-91 Twardy",
    "leo2a6": "Leopard 2A6", "leopard2a4": "Leopard 2A4", "challenger": "Challenger 2",
    "merkava": "Merkava", "ztz99": "ZTZ-99", "amx10rc": "AMX-10 RC", "leclerc": "Leclerc",
    "p4f2": "Panzer IV F2", "m4a3_75mm": "M4A3 Sherman", "m48a1": "M48A1 Patton",
    "f16": "F-16", "f15": "F-15 Eagle", "f18c": "F/A-18C Hornet", "cf18": "CF-18 Hornet",
    "a10a": "A-10A Thunderbolt II", "harrier": "AV-8B Harrier II", "seaharrier": "Sea Harrier",
    "eurofighter": "Eurofighter Typhoon", "mig29": "MiG-29 Fulcrum", "su27": "Su-27 Flanker",
    "su25a": "Su-25 Frogfoot", "su34": "Su-34", "j10": "J-10", "j11b": "J-11B", "fantan": "Q-5 Fantan",
    "a4": "A-4 Skyhawk", "mirage3ea": "Mirage IIIEA", "dagger": "IAI Dagger",
    "tunguska": "2S6 Tunguska", "shilka": "ZSU-23-4 Shilka", "gopher": "SA-13 Gopher",
    "gaskin": "SA-9 Gaskin", "avenger": "M1097 Avenger", "m163": "M163 VADS", "type95": "PGZ-95",
    "spandrel": "9P148 Spandrel", "shturm": "9P149 Shturm-S", "milan": "MILAN",
    "rib": "Lancha RIB", "rib_unarmed": "RIB (desarmada)", "lcvp": "LCVP", "pbr": "PBR",
    "swiftboat": "Swift Boat", "sampan": "Sampán",
    "dirtbike": "Moto de cross", "atv": "Cuatriciclo", "parachute": "Paracaídas",
    # estáticos (code completo)
    "pak40": "Pak 40 (75 mm)", "pak36": "Pak 36 (37 mm)", "zis3": "ZiS-3 (76 mm)",
    "zpu4": "ZPU-4 (AA)", "zu232": "ZU-23-2 (AA)", "45mm_m1937": "45 mm M1937",
    "88mm_flak_18_s": "8,8 cm Flak 18", "2cm_flakvierling_38": "Flakvierling 38 (20 mm)",
    "aaa_rh202": "Rh 202 (20 mm AA)", "aa_m167": "M167 Vulcan", "igla_djigit": "Igla Djigit",
    "sam_tigercat": "Tigercat (SAM)", "usaas_stinger": "Stinger (AA)",
    "stationary_m252": "Mortero M252", "us_m1": "Cañón M1 AT", "static_uav_1": "UAV",
    "spectator_camera_2": "Cámara espectador",
}
VEHICLE_MODELS.update({
    # modelos faltantes (porción tras facción+clase)
    "ka29t": "Ka-29", "dzik": "AMZ Dzik", "hmmwvopen": "HMMWV (descubierto)",
    "hmmwv_uparmored_crows": "HMMWV (blindado, CROWS)", "hmmwv_uparmored_mk19": "HMMWV (blindado, Mk19)",
    "zastava900ak": "Zastava 900 AK", "bmp3m": "BMP-3M", "honker": "Tarpan Honker",
    "skorpion": "Skorpion", "uralzu232": "Ural (ZU-23-2)", "zbik": "Żbik", "vn3": "VN-3",
    "uaz_logistics": "UAZ-469 (logística)", "uaz_spg": "UAZ-469 (SPG-9)", "uaz_alt": "UAZ-469 (alt.)",
    "brdm2_support": "BRDM-2 (apoyo)", "gwagon_support": "G-Wagon (apoyo)",
    "landrover_support": "Land Rover (apoyo)", "landrover_gmg": "Land Rover (GMG)",
    "fennek_mg3": "Fennek (MG3)", "fennek_agl": "Fennek (lanzagranadas)",
    "bushmaster_crows": "Bushmaster (CROWS)", "mengshi_support": "Dongfeng Mengshi (apoyo)",
    "m151a2_support": "M151A2 (apoyo)", "willysmb_mg": "Willys MB (MG)", "ba64": "BA-64",
    "uh1n_m240d": "UH-1N (M240D)", "uh1d_medevac": "UH-1D (MEDEVAC)", "uh60_soar": "UH-60 (160th SOAR)",
    "chinook_ch1": "Chinook HC.1", "chinook_ch47c": "CH-47C Chinook", "z9b": "Z-9B",
    "wessex": "Westland Wessex", "sa341h": "SA341 Gazelle", "sa342": "SA342 Gazelle",
    "ah6a": "AH-6A Little Bird", "uh1c": "UH-1C (cañonera)", "oh6": "OH-6 Cayuse",
    "z10": "Z-10", "z9wa": "Z-9WA", "mtlb": "MT-LB", "mtlb_hmg": "MT-LB (HMG)",
    "mtlb_30mm": "MT-LB (30 mm)", "boragh": "Boragh", "wz551a": "WZ-551A",
    "251c": "Sd.Kfz. 251", "ypr50_gpmg": "YPR-765 (GPMG)", "bwp1": "BWP-1",
    "type86": "Type 86 (WZ-501)", "ba6": "BA-6", "t72av_turms": "T-72AV TURMS-T",
    "m4a3_75mm_dwg": "M4A3 Sherman (faldones)", "m67": "M67 Flame", "m10": "M10 Wolverine",
    "p4d": "Panzer IV D", "p3j": "Panzer III J", "panther_a": "Panther Ausf. A",
    "stug3b": "StuG III B", "leclerc": "Leclerc", "ztl11": "ZTL-11", "type98": "ZTZ-98",
    "f16_cas": "F-16 (CAS)", "cf18_cas": "CF-18 (CAS)", "harrier_gr9_asf": "Harrier GR.9 (ASF)",
    "harrier_gr3": "Harrier GR.3", "seaharrier_mk17": "Sea Harrier (Mk.17)",
    "tornadogr4_mw1": "Tornado GR4 (MW-1)", "mig21": "MiG-21 Fishbed", "mig23": "MiG-23 Flogger",
    "su39": "Su-39", "su22": "Su-22 Fitter", "su30": "Su-30", "j11a": "J-11A",
    "ju87b": "Ju 87 B Stuka", "bf109g6": "Bf 109 G-6", "p51d": "P-51D Mustang",
    "a1h": "A-1 Skyraider", "a4b": "A-4B Skyhawk", "a4c": "A-4C Skyhawk", "a4q": "A-4Q Skyhawk",
    "mirage3ea_as": "Mirage IIIEA (antibuque)", "dagger_cas": "IAI Dagger (CAS)",
    "la5fn": "La-5FN", "i16": "Polikarpov I-16", "il2": "Il-2 Sturmovik",
    "zsu57": "ZSU-57-2", "m3": "M3", "spandrel": "9P148 Spandrel", "wz550": "WZ-550 (HJ-8)",
    "lcvp_logistics": "LCVP (logística)", "lcvp_logi": "LCVP (logística)", "ch_boat": "Lancha (PLA)",
    "hondacb500": "Honda CB500", "c47_para": "C-47 (paracaidistas)",
    # botes (code completo)
    "boat_rib_unarmed": "Lancha RIB (desarmada)", "boat_rib_gpmg_m240b": "Lancha RIB (M240B)",
    "boat_rib_gpmg_pkp": "Lancha RIB (PKP)", "boat_rib_gpmg_c6": "Lancha RIB (C6)",
    "boat_rib_gpmg_l7a2": "Lancha RIB (L7A2)", "boat_rib_gpmg_mg3": "Lancha RIB (MG3)",
    "boat_rib_gpmg_anf1": "Lancha RIB (AA-52)", "boat_rib_hmg_m2": "Lancha RIB (M2 .50)",
    "boat_rib_agl_mk19": "Lancha RIB (Mk19)",
    # emplazamientos desplegables (code completo)
    "deployable_mortar_m252": "Mortero M252", "deployable_mortar_m252_ins": "Mortero M252",
    "deployable_mortar_2b141_podnos": "Mortero 2B14 Podnos", "deployable_mortar_pp87": "Mortero PP87",
    "deployable_tow": "TOW (desplegable)", "deployable_kornet": "9M133 Kornet",
    "deployable_milan": "MILAN", "deployable_milan_mira": "MILAN (MIRA)",
    "deployable_spike": "Spike", "deployable_spike_sp": "Spike SP", "deployable_hj8": "HJ-8",
    "deployable_spg9": "SPG-9", "deployable_djigit": "Igla Djigit", "deployable_stinger": "Stinger",
    "deployable_mistral": "Mistral", "deployable_dshk": "DShK",
    "deployable_50cal_tripod_m2": "M2 .50 (trípode)", "deployable_50cal_tripod_kord": "Kord (trípode)",
    "deployable_50cal_tripod_dshk": "DShK (trípode)", "deployable_50cal_tripod_type85": "Type 85 (trípode)",
    "deployable_mg42": "MG42", "deployable_m1919a6": "M1919A6", "deployable_m1910": "Maxim M1910",
    "deployable_zu232": "ZU-23-2", "deployable_insurgent_hideout": "Escondite (caché)",
    "deployable_kornet_djigit": "Kornet/Djigit",
    "231": "Sd.Kfz. 231", "233": "Sd.Kfz. 233",
    "puma_bf2": "SPz Puma", "stormer": "Stormer (Starstreak)",
    # modelos que aparecían solo como armas de vehículo (kill_weapons)
    "btr60": "BTR-60", "wz551b": "WZ-551B", "zsl92": "ZSL-92", "type95guns": "PGZ-95",
    "fennekswp": "Fennek (SWORD)", "uh1nrockets": "UH-1N Twin Huey",
    "panther": "SdKfz 234 Panther", "m45quad": "M45 Quadmount",
    "bt7": "BT-7", "tornadogr4": "Tornado GR4", "harrierb": "AV-8B Harrier II",
})
# prefijos neutros (no facción) → se tratan por code completo o prettify
VEHICLE_FACTIONS.update({"boat": "", "deployable": "", "static": "", "stationary": "",
                         "parachute": "", "spectator": ""})

_VEHICLE_GENERIC_SUFFIX = {
    "support": "apoyo", "logistics": "logística", "bf2": None, "alt": "alt.",
    "alt2": "alt. 2", "cage": "jaula", "caged": "jaula", "crows": "CROWS",
    "ww2": "2GM", "uparmored": "blindado", "light": "ligero", "militia": "milicia",
    "white": "blanco", "black": "negro", "blue": "azul", "red": "rojo",
    "bomber": "coche bomba", "rocket": "cohetes", "night": "noche", "mg": "MG",
    "gmg": "GMG", "gpmg": "GPMG", "medevac": "MEDEVAC", "navy": "naval",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
# Tokens de relleno (armas de vehículo/emplazadas) → etiqueta o "" para descartar.
_FILLER = {
    "gun": "", "maingun": "", "primarygun": "", "secondarygun": "", "barrel": "",
    "sec": "", "r": "", "g": "", "launcher": "", "missile": "misil", "missle": "misil",
    "pod": "", "rocket": "cohete", "rockets": "cohetes", "mine": "mina", "ied": "IED",
    "coax": "coaxial", "he": "", "ub": "UB", "cannon": "cañón", "tow": "TOW",
    "towlauncher": "lanzador TOW", "atgm": "ATGM", "defence": "defensa", "front": "frontal",
    "back": "trasera", "guns": "", "smallexplosives": "explosivos", "carbomber": "(coche bomba)",
    "bomblauncher": "(lanzador)", "watercontainer": "bidón", "bayonet": "bayoneta",
    "white": "blanco", "black": "negro", "blue": "azul", "red": "rojo",
    "stationary": "", "nobox": "", "cowl": "", "firearm": "", "deployed": "bípode",
    "heat": "HEAT", "frag": "frag", "soviet": "soviética", "alt": "alt.", "night": "noche",
}
_DROP_TOKEN = re.compile(r'^(?:idx|q)\d+$', re.I)
_ACRONYMS = {"apc", "ifv", "ahe", "the", "tnk", "jet", "aav", "sam", "aas", "hmg",
             "gmg", "agl", "lmg", "mmg", "rib", "kni", "uav", "rws"}


def _prettify(token: str) -> str:
    """Fallback legible: separa camelCase/_ , descarta relleno, capitaliza."""
    token = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', token or '')  # camelCase → espacio
    parts = [p for p in re.split(r'[_\s]+', token) if p]
    out = []
    for p in parts:
        pl = p.lower()
        if _DROP_TOKEN.match(pl) or pl in _ACRONYMS:
            if pl in _ACRONYMS:
                continue  # clase de vehículo redundante en una etiqueta de arma
            continue
        if pl in _FILLER:
            if _FILLER[pl]:
                out.append(_FILLER[pl])
            continue
        out.append(p.upper() if len(p) <= 3 else p.capitalize())
    return " ".join(out) if out else (token.strip() or "?")


def _longest_prefix(code: str, keys) -> Optional[str]:
    best = None
    for k in keys:
        if code.startswith(k) and (best is None or len(k) > len(best)):
            best = k
    return best


def _tokenize_attachments(tail: str) -> str:
    """Convierte 'elcandeployed' / '1p78' / 'scope' en una etiqueta de variante."""
    if not tail:
        return ""
    labels = []
    # primero intenta tokens separados por _
    for chunk in re.split(r'[_\s]+', tail):
        if not chunk:
            continue
        # consume tokens conocidos pegados (p.ej. 'elcandeployed')
        s = chunk
        consumed = []
        while s:
            for tok in sorted(WEAPON_ATTACHMENTS, key=len, reverse=True):
                if s.startswith(tok):
                    consumed.append(WEAPON_ATTACHMENTS[tok])
                    s = s[len(tok):]
                    break
            else:
                # token no reconocido: usa el resto crudo y corta
                consumed.append(_prettify(s))
                s = ""
        labels.extend([c for c in consumed if c])
    # dedup preservando orden
    seen = set()
    out = [x for x in labels if not (x in seen or seen.add(x))]
    return ", ".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Resolvers
# ─────────────────────────────────────────────────────────────────────────────
# Asientos de vehículo (PLAYER_UPDATE.vehicle.seat_name) → etiqueta legible.
SEAT_NAMES = {
    "driver": "Conductor", "pilot": "Piloto", "copilot": "Copiloto",
    "co-pilot": "Copiloto", "gunner": "Artillero", "passenger": "Pasajero",
    "commander": "Comandante",
}


def resolve_seat(code: str) -> str:
    low = (code or "").lower()
    for key, label in SEAT_NAMES.items():
        if key in low:
            return label
    return _prettify(code) or "Asiento"


def resolve_gamemode(code: str) -> str:
    return GAMEMODES.get((code or "").lower(), _prettify(code))


def resolve_map(code: str) -> str:
    if code in MAPS:
        return MAPS[code]
    base = re.sub(r'_\d+$', '', code or '')  # quita sufijo de versión
    return MAPS.get(base, _prettify(code) if code else "—")


def resolve_kit(code: str) -> str:
    c = (code or "").lower()
    rest = _KIT_VARIANT_SUFFIX.sub('', c)
    # quitar facción inicial para acotar el match de rol
    parts = rest.split('_')
    if parts and parts[0] in KIT_FACTIONS:
        rest = rest[len(parts[0]):]
    for key in _ROLE_KEYS:
        if key in rest:
            return KIT_ROLES[key]
    # gungame y otros sin rol claro
    if "gungame" in c:
        return "Gun Game"
    return _prettify(code) or "Desconocido"


def resolve_weapon(code: str) -> dict:
    if code in WEAPON_SPECIAL:
        label, kind = WEAPON_SPECIAL[code]
        return {"model": label, "variant": "", "label": label, "kind": kind}
    c = (code or "")
    low = c.lower()
    # cuerpo a cuerpo / explosivos colocables (cuchillos, C4, minas, IED…)
    for key, (kind, base) in _MELEE_EXPLOSIVE.items():
        if low.startswith(key) or low.startswith("ins" + key) or ("_" + key) in low:
            extra = _prettify(re.sub(r'(?:^|_)' + re.escape(key) + r'_?', '', low))
            label = f"{base} ({extra})" if extra and extra != "?" else base
            return {"model": base, "variant": extra if extra != "?" else "", "label": label, "kind": kind}
    # armas de vehículo / emplazadas: kind=vehicle (sin cambios para no romper la
    # exclusión de "arma personal"), + el vehículo/emplazamiento que la porta.
    if low.startswith(_VEHICLE_WEAPON_PREFIXES) or any(h in low for h in _VEHICLE_WEAPON_HINTS):
        vw = resolve_vehicle_weapon(c)
        lab = vw["vehicle"]
        return {"model": lab, "variant": "", "label": lab, "kind": "vehicle",
                "vehicle": vw["vehicle"], "vclass": vw["vclass"], "vtype": vw["vtype"]}
    prefix = _longest_prefix(low, WEAPON_PREFIXES)
    if prefix:
        faction, kind = WEAPON_PREFIXES[prefix]
        tail = low[len(prefix):].lstrip('_')
    else:
        faction, kind, tail = None, "unknown", low
    model_key = _longest_prefix(tail, WEAPON_MODELS)
    if model_key:
        model = WEAPON_MODELS[model_key]
        variant = _tokenize_attachments(tail[len(model_key):].lstrip('_'))
    else:
        model = _prettify(tail) or _prettify(c)
        variant = ""
    label = f"{model} ({variant})" if variant else model
    # corregir kind para granadas/explosivos detectados por modelo
    if kind in (None, "unknown") and ("Granada" in model or "Mina" in model):
        kind = "grenade" if "Granada" in model else "explosive"
    return {"model": model, "variant": variant, "label": label, "kind": kind or "unknown"}


def resolve_vehicle(code: str) -> dict:
    c = (code or "")
    if c in VEHICLE_MODELS:
        return {"model": VEHICLE_MODELS[c], "class": "", "label": VEHICLE_MODELS[c], "kind": ""}
    parts = c.split('_')
    faction = VEHICLE_FACTIONS.get(parts[0]) if parts else None
    cls_label, kind = "", ""
    model_key = c
    if len(parts) >= 3 and parts[1] in VEHICLE_CLASSES:
        cls_label, kind = VEHICLE_CLASSES[parts[1]]
        model_key = "_".join(parts[2:])
    elif len(parts) == 2:
        model_key = parts[1]
    model = VEHICLE_MODELS.get(model_key)
    if model is None:
        # intenta quitar sufijos genéricos (support/logistics/bf2/alt…)
        toks = model_key.split('_')
        base = toks[0]
        extra = [_VEHICLE_GENERIC_SUFFIX.get(t, t) for t in toks[1:]]
        base_name = VEHICLE_MODELS.get(base, _prettify(base))
        extra = [e for e in extra if e]
        model = f"{base_name} ({', '.join(extra)})" if extra else base_name
    label = model
    return {"model": model, "class": cls_label, "label": label, "kind": kind}


def _strip_vehicle_weapon_tail(tokens: list) -> list:
    """Corta los tokens de cola (parte del arma) para quedarse con el modelo."""
    out = []
    for t in tokens:
        if t in _VEHICLE_WEAPON_TAIL or re.match(r'^\d+mm$', t):
            break
        out.append(t)
    return out


def _model_from_tokens(after: list) -> Optional[str]:
    """Busca el match de modelo más largo (VEHICLE_MODELS) en los tokens dados."""
    for k in range(len(after), 0, -1):
        cand = "_".join(after[:k])
        if cand in VEHICLE_MODELS:
            return VEHICLE_MODELS[cand]
    return None


def resolve_vehicle_weapon(code: str) -> dict:
    """Mapea un arma montada/emplazada al vehículo o emplazamiento que la porta.

    Devuelve {'vehicle': <nombre>, 'vclass': 'vehicle'|'emplacement',
    'vtype': 'ground'|'air'|'naval'|'emplacement'}. Pensado para agrupar
    `kill_weapons` en "kills con vehículos" sin la contaminación de `vehicle_kills`
    (que cuenta kills a pie tras desmontar) y para el desglose por tipo (-assets)."""
    low = (code or "").lower()

    # Emplazamientos estáticos / desplegables.
    if low.startswith(_EMPLACEMENT_WEAPON_PREFIXES):
        toks = low.split('_')
        name = _model_from_tokens(toks)
        if name is None:
            for i, t in enumerate(toks):
                if t in VEHICLE_CLASSES:
                    name = _model_from_tokens(_strip_vehicle_weapon_tail(toks[i + 1:]))
                    break
        if name is None:
            body = [t for t in toks if t not in ("deployable", "static", "stationary")]
            name = _prettify("_".join(_strip_vehicle_weapon_tail(body))) or "Emplazamiento"
        return {"vehicle": name, "vclass": "emplacement", "vtype": "emplacement"}

    toks = low.split('_')
    # Code estructurado facción?_clase_modelo_arma.
    for i, t in enumerate(toks):
        if t in VEHICLE_CLASSES:
            emplaced = t in _EMPLACEMENT_CLASSES
            vclass = "emplacement" if emplaced else "vehicle"
            vtype = "emplacement" if emplaced else _VTYPE_BY_CLASS_KIND.get(
                VEHICLE_CLASSES[t][1], "ground")
            after = toks[i + 1:]
            name = _model_from_tokens(after)
            if name is None:
                name = _prettify("_".join(_strip_vehicle_weapon_tail(after))) or _prettify(t)
            return {"vehicle": name, "vclass": vclass, "vtype": vtype}

    # Legacy CamelCase (token0 = vehículo). Históricamente son coaxiales de
    # tanques/APC → terrestres.
    t0 = toks[0]
    if t0 in VEHICLE_MODELS:
        return {"vehicle": VEHICLE_MODELS[t0], "vclass": "vehicle", "vtype": "ground"}
    if t0 in _LEGACY_VEHICLE_WEAPON:
        return {"vehicle": _LEGACY_VEHICLE_WEAPON[t0], "vclass": "vehicle", "vtype": "ground"}
    name = _prettify("_".join(_strip_vehicle_weapon_tail(toks))) or _prettify(code)
    return {"vehicle": name, "vclass": "vehicle", "vtype": "ground"}


# ─────────────────────────────────────────────────────────────────────────────
# Generación del manifest
# ─────────────────────────────────────────────────────────────────────────────
def build_aliases(player_details: list, map_stats: list) -> dict:
    """Resuelve todos los codes presentes en la data → dict para aliases.json."""
    kit_codes, weapon_codes, veh_codes, seat_codes = set(), set(), set(), set()
    for r in player_details or []:
        kit_codes.update((r.get("kits_used") or {}))
        weapon_codes.update((r.get("kill_weapons") or {}))
        weapon_codes.update((r.get("death_weapons") or {}))
        veh_codes.update((r.get("vehicle_kills") or {}))
        veh_codes.update((r.get("vehicles_destroyed_by_type") or {}))
        seat_codes.update((r.get("seat_kills") or {}))
    map_codes, gm_codes = set(), set()
    for m in map_stats or []:
        map_codes.add(m.get("map_name", ""))
        gm_codes.add(m.get("gamemode", ""))
    return {
        "gamemodes": {c: resolve_gamemode(c) for c in sorted(gm_codes)},
        "maps": {c: resolve_map(c) for c in sorted(map_codes)},
        "kits": {c: resolve_kit(c) for c in sorted(kit_codes)},
        "weapons": {c: resolve_weapon(c) for c in sorted(weapon_codes)},
        "vehicles": {c: resolve_vehicle(c) for c in sorted(veh_codes)},
        "seats": {c: resolve_seat(c) for c in sorted(seat_codes)},
    }

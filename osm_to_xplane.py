"""
Created on Thu Mar 28 21:25:25 2024

@author: Saar Nagar

Links:
https://www.airops.com/blog/calculating-distance-between-two-points-in-sql
https://overpass-turbo.eu/#
https://www.sqlitetutorial.net/sqlite-python/
https://docs.python.org/3/library/sqlite3.html


Roofs:
https://wiki.openstreetmap.org/wiki/Simple_3D_Buildings
https://blendermarket.com/products/gn-roof-generator
https://blender.stackexchange.com/questions/14136/trying-to-create-a-script-that-makes-roofs-on-selected-boxes

Calculate Normals
https://gamedev.net/forums/topic/330992-vertex-normals-in-wavefront-objs/
"""

import math
import re
import shutil
import sqlite3
from math import trunc
from sqlite3 import Error
import json
import copy
import os
import os.path
from pathlib import Path
import sys
import platform
import time
import subprocess
from subprocess import CalledProcessError

import requests
from requests.exceptions import HTTPError
from dataclasses import dataclass
from typing import Dict, Any


G_MAJOR_VER = 2025
G_MINOR_VER = 8
G_FIX_VER = 1
G_VERSION = f"{G_MAJOR_VER}.{G_MINOR_VER}.{G_FIX_VER}"

# G_DB_FILE = "osmdb.sqlite"
G_DB_FILE = "osmdb"
G_TEMP_FOLDER = "temp"  # v25.08.1

G_TABLES = {}
G_NODES_TABLE = "nodes"
G_WAYS_TABLE = "ways"
G_WAYS_META_TABLE = "ways_meta"
G_OBJ8_DATA_TABLE = "obj8_data"

# G_OUTPUT_OBJ_FILES_NAME = "obj_files.txt"
# G_OUTPUT_OBJ_RESUME_FILES_NAME = "obj_resume_files.txt"

G_PREPARED_FILES_TO_PROCESS = 0
G_SKIPPED_FILES = 0

CONFIG_MODE = "mode"
CONFIG_OBJ_FILTER = "mode_obj_filter_text"
CONFIG_HELIPAD_FILTER = "mode_helipad_filter_text"
CONFIG_OUT_FOLDER = "out_folder"
CONFIG_OSM_BBOX = "osm_bbox"
CONFIG_OSM_JSON_FILE = "osm_json_file"
CONFIG_DEBUG_WAY_ID = "debug_way_id"
CONFIG_LIMIT = "limit"
CONFIG_QUERY_META_TEXT = "query_meta_text"
CONFIG_HEIGHT_KEYS_LIST = "height_keys_list"
CONFIG_BLENDER_BIN = "blender_bin"
CONFIG_MAX_WALL_LENGTH = "max_wall_length"
CONFIG_SQLITE_SUPPORT_MATH = "sqlite_support_math"
CONFIG_FILTER_OUT_OBJ_WITH_PERIMETER_GREATER_THAN = "filter_out_obj_with_perimeter_greater_than"
CONFIG_FILTER_OUT_OBJ_WITH_PERIMETER_LESS_THAN = "filter_out_obj_with_perimeter_less_than"
CONFIG_FILTER_IN_OBJ_WITH_PERIMETER_BETWEEN = "filter_in_obj_with_perimeter_between"
CONFIG_FILTER_OUT_EVERY_NTH_MESH = "filter_out_every_nth_mesh"
CONFIG_OUTPUT_FOLDER_FOR_THE_DSF_TEXT = "output_folder_for_the_dsf_text"
CONFIG_ROOT_SCENERY_FOLDER_TO_COPY_OBJ8_FILES = "root_scenery_folder_to_copy_obj8_files"
CONFIG_LIB_RELATIVE_PATH = "lib_relative_path"
CONFIG_SCRIPT_WORK_FOLDER = "script_work_folder"  # default is out
CONFIG_WORK_FOLDER = "work_folder"  # Holds the working folder path based on "CONFIG_SCRIPT_WORK_FOLDER"
CONFIG_WORK_FOLDER_IS_ABSOLUTE_PATH = "work_folder_is_absolute_path"  # boolean if work folder is absolute or not
CONFIG_USE_SQLITE_FLOW = "use_sqlite_flow"  # boolean if to use the code logic that stores and filter most data from the sqlite DB
CONFIG_OVERPASS_URL = "overpass_url"  # holds the preferred overpass url to connect too.
CONFIG_REQUEST_TIMEOUT = "request_timeout"  # v25.08.1 holds the timeout request from overpass
CONFIG_LOG_FOLDER = "log_folder"  # v25.05.1 holds the log folder location

CONF_OUTPUT_OBJ_FILES = "obj_files"  # "obj_files.txt" => "obj_files_{bbox}.txt"
CONF_OUTPUT_OBJ_RESUME_FILES_NAME = "obj_resume_files"  # "obj_resume_files.txt" => "obj_resume_files_{bbox}.txt"
CONF_OUTPUT_OSM_TO_OBJ_BLEND_LOG_FILENAME = "osm_to_obj_blend_log"  # holds the blender output log file name and path

OPT_MODE_OBJ = "obj"  # this is also the default
OPT_MODE_HELIPAD = "helipad"

# v1.1
CONFIG_SKIP_RULE = "skip_rule"  # When resume work because of fail, do we want to skip already processed files ?
# G_RESUME_LIST = [5, 10]  # 5: wavefront, 10: before calling blender

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_INPUT_DSF_TEMPLATE_FILE_NAME = "dsf_template.tmpl"
DEFAULT_DSF_TEXT_OUTPUT_FILE_NAME = "dsf_obj8"  # Will be created in the main script folder. Can be modified by "blend_export_xplane_output_folder"
DEFAULT_REQUEST_TIMEOUT = 30  # v25.08.1

DEFAULT_LIMIT_FILES = 1000
DEFAULT_LOG_FOLDER = "logs"  # v25.05.1

K_PERIMETER = "perimeter"
K_MT_DISTANCE = "mt_distance"
K_WAY_ID = "way_id"
K_LAT = "lat"
K_LON = "lon"
K_SEQ = "seq"
K_MAX_SEQ = "max_seq"
K_TETA1 = "teta1"
K_TETA2 = "teta2"
K_DELTA2 = "delta2"
K_LEAD_LAT = "lead_lat"
K_LEAD_LON = "lead_lon"
K_DEGREES_ROUND = "degrees_round"
K_FILE_NAME_OSM = "file_name_osm"
K_FILE_NAME_OBJ8 = 'file_name_obj8'
K_SIMILAR_TO_WAY_ID = 'similar_to_way_id'
K_ROTATION = 'rotation'


# ----------------------------------------
# -  Class Point         -----------------
# ----------------------------------------

# The dataclass to store the coordinates of the center.
@dataclass
class Coordinate:
    """A dataclass to hold latitude and longitude."""
    lat: float
    lon: float

    def distance_to(self, other_coordinate) -> float:
        """
        Calculates the distance between this coordinate and another coordinate
        using the Haversine formula. The result is in meters.

        Args:
            other_coordinate (Coordinate): The other coordinate object to measure
                                           the distance to.

        Returns:
            float: The distance in meters.
        """
        R = 6371000.0  # Radius of Earth in meters

        lat1_rad = math.radians(self.lat)
        lon1_rad = math.radians(self.lon)
        lat2_rad = math.radians(other_coordinate.lat)
        lon2_rad = math.radians(other_coordinate.lon)

        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance_meters = R * c
        return distance_meters


# The dataclass to hold the results for each "way".
@dataclass
class WayCenter:
    """A dataclass to store the name and calculated center of a way."""
    name: str
    center: Coordinate

    tags: Dict[str, str]
    meta_1302: Dict[str, str]

    width_mt: int = 10
    height_mt: int = 10

    heliport_header_17: str = ""
    heliport_info_102: str = ""
    heliport_meta_1302: str = ""




# ----------------------------------------
# -  END CLASS           -----------------
# ----------------------------------------


def print_help():
    """
  Print the help text.
  Should consider deprecating it.
  """

    help01 = """Basic syntax:
SCRIPT [config.json | {path to param_file}.json ]

Due to the list of variable options, you have to modify the "config.json" file
or create your own "custom".json file with the

examples:
$ {sys.argv[0]}
$ {sys.argv[0]} myconfig.json


"""
    print("\n", sys.argv[0], " - Help:\n")
    print(help01)

    sys.exit()


def read_config_file():
    """ Function Reads the config file. """

    # limit_files = 0 # Deprecated, defined in the config.json
    config_file = "config.json"
    loc_dc_config = {}
    if len(sys.argv) > 1:
        config_file = sys.argv[1]

    # load config #
    try:
        with open(config_file, 'r', encoding='utf8') as json_file:
            s_buffer = ""  # Initialize an empty string to store non-commented lines
            for line in json_file:
                trimmed_line = line.strip()  # Remove leading/trailing whitespaces
                if not trimmed_line.startswith("//"):
                    s_buffer += trimmed_line + "\n"  # Append non-commented lines to sBuffer

        try:
            loc_dc_config = json.loads(s_buffer)  # init the dictionary
        except json.JSONDecodeError as json_error:
            print(f'Error in "{config_file}" file.\n{json_error}')
            sys.exit(1)

        # if loc_dc_config.get(CONFIG_LIMIT, 0) > 0:
        #     limit_files = loc_dc_config.get(CONFIG_LIMIT)

        if loc_dc_config.get(CONFIG_DEBUG_WAY_ID) is not None and not isinstance(loc_dc_config.get(CONFIG_DEBUG_WAY_ID),
                                                                                 list):
            print(
                f"[ERROR] You defined {CONFIG_DEBUG_WAY_ID} with wrong type, Current type is: {type(loc_dc_config[CONFIG_DEBUG_WAY_ID])}.\nShould be a list with one or more number values.\nExample: {CONFIG_DEBUG_WAY_ID} : [54321, 65432],")
            sys.exit()

    except OSError as os_err:
        print(f"{os_err}\n")
        print(f"[Error] Failed to read file: {config_file} !\n\n")
        print_help()  # will also exit from the program #

    return loc_dc_config


def is_number(test_string):
    # Regular expression to match a number format, including optional feet/inches or quotes
    pattern = r"^\d+(\.\d+)?(['\"‘’″′]*)$"  # Matches numbers with optional quotes/units
    return bool(re.match(pattern, test_string.strip()))


def parse_feet_inches(test_string):
    try:
        # Replace quotes with spaces and split
        parts = re.split(r"[\'\"]", test_string.strip())
        parts = [p for p in parts if p]  # Remove empty parts
        # Convert parts to numbers
        values = [float(p) for p in parts]
        return True, values
    except ValueError:
        return False, None


def init_tables_metatdata():
    """ Initialize SQLite tables.
Uses G_xxx_TABLE globals as keys.
The name of the "key" must be the same as the "table" name
  """

    G_TABLES[G_NODES_TABLE] = f"""
        CREATE TABLE IF NOT EXISTS {G_NODES_TABLE} (
            node_id integer PRIMARY KEY,
            lat real,
            lon real
        )
    """

    G_TABLES[G_WAYS_TABLE] = f"""
        CREATE TABLE IF NOT EXISTS {G_WAYS_TABLE} (
            seq integer,
            way_id integer,
            node_id integer
        )
    """

    G_TABLES[G_WAYS_META_TABLE] = f"""
        CREATE TABLE IF NOT EXISTS {G_WAYS_META_TABLE} (
            way_id integer,
            k text,
            v text,
            PRIMARY KEY (way_id, k)
        )
    """

    # Stores data processed in blender and then analyzed and optimize to find duplicate like obj8 files with same shape/dimensions
    G_TABLES[G_OBJ8_DATA_TABLE] = f"""
        CREATE TABLE IF NOT EXISTS {G_OBJ8_DATA_TABLE} (
            seq integer,
            way_id integer,
            lat real,
            lon real,
            file_name_osm text,
            file_name_obj8 text,
            edges integer,
            edges_length text,
            edges_length_real text,
            similar_to_way_id integer,
            rotation integer,
            PRIMARY KEY (way_id)
        )
    """


def post_overpass_index_creation(conn):
    stmt = f"CREATE INDEX if not exists {G_NODES_TABLE}_indx on {G_NODES_TABLE}(node_id)"
    exec_stmt(conn, stmt)

    stmt = f"CREATE INDEX if not exists {G_WAYS_TABLE}_indx on {G_WAYS_TABLE}(way_id, seq)"
    exec_stmt(conn, stmt)

    stmt = f"CREATE INDEX if not exists {G_WAYS_META_TABLE}_indx on {G_WAYS_META_TABLE}(way_id)"
    exec_stmt(conn, stmt)

    stmt = "drop view if exists ways_nodes_vu"
    exec_stmt(conn, stmt)

    stmt = '''create view if not exists ways_nodes_vu
as
select w.seq, w.way_id, n.*
from ways w
inner join nodes n
on w.node_id = n.node_id
where 1 = 1
'''
    exec_stmt(conn, stmt)


def create_tables(conn):
    if conn:
        for stmt in G_TABLES.values():  # .items():
            exec_stmt(conn, stmt)


def create_db(in_dc_config: dict):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(in_dc_config.get("db_file"))

        # conn.create_function('sqrt', 1, math.sqrt) # Register math functions from python
        # conn.create_function('degrees', 1, math.degrees) # Register math functions from python
        # conn.create_function('radians', 1, math.radians) # Register math functions from python
        # conn.create_function('sin', 1, math.sin) # Register math functions from python
        # conn.create_function('cos', 1, math.cos) # Register math functions from python
        # conn.create_function('abs', 1, math.fabs) # Register math functions from python
        # conn.create_function('atan2', 2, math.atan2) # Register math functions from python
        # conn.create_function('pow', 2, math.pow) # Register math functions from python

        # print(sqlite3.version) ## removed since it is deprecated since python v3.12
        return conn
    except Error as e:
        print(e)

    return conn


def exec_stmt(conn, stmt: str, in_binds: list = None):
    if in_binds is None:
        in_binds = []

    if conn:
        try:
            c = conn.cursor()
            c.execute(stmt, in_binds)
        except Error as e:
            print(e)
            print(f"Stmt: {stmt}\nBinds: {in_binds}")


def exec_query_stmt(conn, stmt, in_binds=None, b_fetch_all=True):
    """
  Parameters
  ----------
  conn : SQLite connection type
      Valid connection to SQLite database file.
  stmt : String
      The query to execute.
  b_fetch_all : Boolean.
      Fetch all rows or only one. The default is True = all rows.
  in_binds : Array, optional
      Array of bind variables. The default is an empty array [].

  Returns
  -------
  If b_fetch_all = True:
      Returns list of dictionary rows.
      Can access: rows[0]['col name']
  If b_fetch_all = False:
      Returns a Dictionary
      Can access: rows['col name']
          Field Name, Value

  """
    if in_binds is None:
        in_binds = []

    if conn:
        try:
            # https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(stmt, in_binds)
            if b_fetch_all:
                return c.fetchall()

            return c.fetchone()
        except Error as e:
            print(e)
            print(f"Stmt: {stmt}\nBinds: {in_binds}")

    return None


def drop_all_tables(conn):
    if conn:
        for key in G_TABLES.keys():
            stmt = f"DROP TABLE if exists {key}"
            exec_stmt(conn, stmt)


def check_skip_and_resume_settings(in_dc_config: dict, in_resume_lvl_needed: int, in_output_file, in_output_file_obj8,
                                   lon_lat_way_id_s):
    global CONF_OUTPUT_OBJ_RESUME_FILES_NAME

    # Check if file exists and larger than 500 bytes then skip.
    if in_dc_config.get(CONFIG_SKIP_RULE, "") != "" and in_dc_config.get(CONFIG_SKIP_RULE, 0) == 5:
        if Path(in_output_file_obj8).exists() and Path(in_output_file_obj8).stat().st_size > 500:
            print(f'SKIPPING file: {in_output_file!r} because {in_output_file_obj8!r} exists. Based on filter...')

            with open(file=in_dc_config.get(CONF_OUTPUT_OBJ_RESUME_FILES_NAME), mode="a", encoding="utf8") as text_file:
                text_file.write(f'{in_output_file_obj8}|{lon_lat_way_id_s}\n')  # will be used after DSF
                return True

    return False


def parse_osm_node(conn=object(), in_dict=None):
    if in_dict is None:
        in_dict = {}

    binds = [in_dict['id'], in_dict['lat'], in_dict['lon']]
    stmt = f"insert into {G_NODES_TABLE} (node_id, lat, lon) values (?, ?, ?)"
    exec_stmt(conn, stmt, binds)


def parse_osm_way(conn=object(), in_dict=None):
    if in_dict is None:
        in_dict = {}

    seq = 1
    way_id = in_dict["id"]
    binds = []

    for v in in_dict['nodes']:  # Loop over the array of nodes
        binds = [seq, way_id, v]
        stmt = f"insert into {G_WAYS_TABLE} (seq, way_id, node_id) values (?, ?, ?)"
        exec_stmt(conn, stmt, binds)
        binds.clear()

        seq += 1

    # Read <tag>s
    binds.clear()
    if in_dict.get("tags") is not None:
        for k, v in in_dict["tags"].items():
            binds = [in_dict["id"], k, v]  # loop over the "tags" dictionary
            stmt = f"insert into {G_WAYS_META_TABLE} (way_id, k, v) values (?, ?, ?)"
            exec_stmt(conn, stmt, binds)
            binds.clear()


def get_helipad_metadata(json_data: dict) -> list[WayCenter]:
    """
    Extracts 'way' elements from JSON data, finds their nodes,
    and calculates the geographic center of each way.

    Args:
        json_data (dict): The dictionary parsed from the JSON file.

    Returns:
        List[WayCenter]: A list of WayCenter objects, each containing the name
                         of the way and its calculated center coordinate.
    """
    # Create a dictionary for quick lookup of node coordinates by ID.
    node_lookup = {}
    for element in json_data.get("elements", []):
        if element.get("type") == "node":
            node_lookup[element.get("id")] = {
                "lat": element.get("lat"),
                "lon": element.get("lon")
            }

    all_helipads_metadata = []
    vector_length_list = []

    # Iterate through all elements to find "way" types with a "nodes" key.
    for element in json_data.get("elements", []):
        if element.get("type") == "way" and "nodes" in element: ## and element.get("tags", {}).get("name", "") != "":
            way_name = element.get("tags", {}).get("name", "")
            node_ids = element.get("nodes")

            vector_length_list.clear()

            # Initialize sums for latitude and longitude
            total_lat = 0.0
            total_lon = 0.0

            # Extract coordinates for all nodes in the current way.
            # We use a list to store coordinates to count them later.
            coordinates_in_way = []
            prev_point = Coordinate(lat=0.0, lon=0.0)
            for node_id in node_ids:
                if node_id in node_lookup:
                    coords = node_lookup[node_id]
                    coordinates_in_way.append(coords)
                    current_point = Coordinate( lat=coords['lat'], lon=coords['lon'])
                    if prev_point.lat * prev_point.lon != 0.0:
                        vector_length_list.append(prev_point.distance_to(current_point))

                    prev_point = Coordinate(lat=current_point.lat, lon=current_point.lon)

            vector_length_list.sort(reverse=True)

            # If the way has valid nodes, calculate the center.
            if coordinates_in_way:
                for coords in coordinates_in_way:
                    total_lat += coords["lat"]
                    total_lon += coords["lon"]

            # Calculate the centre coordinates
            num_nodes = len(coordinates_in_way)

            center_lat = total_lat / num_nodes
            center_lon = total_lon / num_nodes

            # Sort the coordinates in clockwise order around the center
            try:
                tags = element.get("tags")

                coordinates_in_way.sort(key=lambda coord: math.atan2(coord['lat'] - center_lat, coord['lon'] - center_lon), reverse=True)

                # Create a WayCenter object and add it to our results list.
                center_coord = Coordinate(lat=center_lat, lon=center_lon)
                helipad_data = WayCenter(name=way_name, center=center_coord, tags=tags, meta_1302={"name" : way_name})

                # store all tags
                for k, v in tags.items():
                    # helipad_data.tags[k] = v
                    key = str.lower(k)

                    search_key_list = ["faa", "iata", "icao", "name:en", "emergency", "operator"]
                    for search_key in search_key_list:
                        if search_key in key:
                            if search_key == "faa":
                                helipad_data.meta_1302["faa_code"] = v
                            elif search_key == "iata":
                                helipad_data.meta_1302["iata_code"] = v
                            elif search_key == "icao":
                                helipad_data.meta_1302["icao_code"] = v
                            else:
                                helipad_data.meta_1302[key] = v


                # Calculate Width and Height
                if len(vector_length_list) > 0:  # at least three points
                    helipad_data.width_mt = int(vector_length_list[0]) if int(vector_length_list[0]) > 9 else 10  # limit size to 10 meters or above
                    helipad_data.height_mt = helipad_data.width_mt

                all_helipads_metadata.append(helipad_data)
            except Exception as any_error:
                print(any_error)

    return all_helipads_metadata


def get_osm_airport_id (local_id: str, navaid: WayCenter) -> str:
    search_key_list = ["faa_code", "iata_code", "icao_code", "faa", "iata", "icao"]
    for search_key in search_key_list:
        if search_key in navaid.meta_1302.keys():
            return navaid.meta_1302[search_key]

    return local_id

def parse_osm_helipad_nodes(in_dc_config: dict, in_data: dict) -> None:
    current_time_string = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())

    apt_dat_header = f'''I
1200 Generated by {os.path.basename(__file__)}
'''
    heliport_template_17 = f'17   0 0 0 id heliport_name'
    heliport_102 = '102  ramp_name centre_lat centre_lon 0 width height 2 0 0 0.00 0'  # WxH=10.0

    node_counter = 0
    osm_filter_list = []  # return array of osm <way> ids
    osm_node_id_tags = {}  # dictionary of way_id and sub dictionary of {tags} = { way_id, {tags}}

    osm_helipads_list = get_helipad_metadata(in_data)

    if osm_helipads_list:
        # Write apt.dat
        current_folder = os.getcwd()
        output_folder = in_dc_config.get(CONFIG_WORK_FOLDER, current_folder)
        output_custom_scenery_folder = in_dc_config.get(CONFIG_ROOT_SCENERY_FOLDER_TO_COPY_OBJ8_FILES, "")


        postfix = in_dc_config.get(CONFIG_OSM_BBOX, '').replace(',', '_')
        filename = f'apt_dat_helipads_[{postfix}].dat'
        output_work_folder_apt_dat_file = os.path.join(output_folder, filename)
        output_custom_scenery_file_and_path = os.path.join(output_custom_scenery_folder, filename)

        # Create the original custom apt.dat file in the working folder
        with open(output_work_folder_apt_dat_file, 'w', encoding='utf8') as apt_dat_text_out:

            # write apt.dat header once
            apt_dat_text_out.write(f'{apt_dat_header}\n\n')
            ramp_seq = 0  # should not exceed 99, example "H99", max characters allowed is three (3)
            max_allowed_helipads: int = 99999
            for indx, way_info in enumerate(osm_helipads_list):
                seq = indx + 1  # used with ramp_name and custom meta icao_code
                ramp_seq = ramp_seq + 1 if (ramp_seq + 1 ) < 100 else 1

                # Stop if seq reached 10000
                sys.exit(f"\n!!! Reached Max number of helipad to process: {max_allowed_helipads}. Currently reached {seq}  !!!\n") if seq > max_allowed_helipads else None

                local_id = f'XOX{seq:04d}' if seq < 10000 else f'XO{seq:05d}'
                way_info.name = f'OSM {str.title("to xplane")} {seq}' if way_info.name == "" else way_info.name.title()[:29]  # limit to 29 characters
                # way_info.name = str.title( f'osm to xplane {seq}') if way_info.name == "" else way_info.name.title()[:29]  # limit to 29 characters

                local_id = get_osm_airport_id(local_id=local_id, navaid=way_info)

                print(f"Way Name: {way_info.name}")
                print(f"Calculated Center: Lat={way_info.center.lat:.6f}, Lon={way_info.center.lon:.6f}\n")


                way_info.heliport_header_17 = heliport_template_17
                way_info.heliport_info_102 = heliport_102

                way_info.heliport_header_17 = way_info.heliport_header_17.replace("id", local_id.upper())
                way_info.heliport_header_17 = way_info.heliport_header_17.replace("heliport_name", way_info.name)

                way_info.heliport_info_102 = way_info.heliport_info_102.replace("ramp_name", f'H{ramp_seq}')
                way_info.heliport_info_102 = way_info.heliport_info_102.replace("centre_lat", str(way_info.center.lat))
                way_info.heliport_info_102 = way_info.heliport_info_102.replace("centre_lon", str(way_info.center.lon))
                way_info.heliport_info_102 = way_info.heliport_info_102.replace("width", str(way_info.width_mt))
                way_info.heliport_info_102 = way_info.heliport_info_102.replace("height", str(way_info.height_mt))

                print(f'{way_info.heliport_header_17}')
                print(f'{way_info.heliport_info_102}')

                apt_dat_text_out.write(f'{way_info.heliport_header_17}\n')
                # add 1302 meta data
                for k, v in way_info.meta_1302.items():
                    apt_dat_text_out.write(f'1302 {k} {v}\n')

                if "icao_code" not in way_info.meta_1302 and "iata_code" not in way_info.meta_1302 and "faa_code" not in way_info.meta_1302:
                    apt_dat_text_out.write(f'1302 local_code {local_id}\n')
                    apt_dat_text_out.write(f'1302 gui_label 2D\n')
                    apt_dat_text_out.write(f'1302 generated_by osm_to_xplane Saar.N\n')

                apt_dat_text_out.write(f'{way_info.heliport_info_102}\n')

                apt_dat_text_out.write('\n')
                if indx == (len(osm_helipads_list) - 1):
                    apt_dat_text_out.write("99\n")  # last line in apt.dat file

        print(f'\n>> Processed {len(osm_helipads_list)} helipads <<\n')
        # Copy to scenery folder
        if output_custom_scenery_folder != "":
            with open(output_custom_scenery_file_and_path, 'w', encoding='utf8') as custom_apt_dat_out:
                with open(output_work_folder_apt_dat_file, 'r', encoding='utf8') as apt_dat_text_in:
                    custom_apt_dat_out.write(apt_dat_text_in.read())

    else:
        print("No '<way>' elements with valid node data were found in the JSON output.")


# def process_osm_helipad_nodes(db, in_dc_config: dict, main_osm_id_list: list):


def parse_osm_building_nodes(conn, in_dc_config: dict, in_data: dict) -> list[Any]:
    node_counter = 0
    osm_filter_list = []  # return array of building ids
    osm_node_id_tags = {}  # dictionary of way_id and sub dictionary of {tags} = { way_id, {tags}}

    try:
        # # Process the retrieved buildings into its nodes (points like lat/lon)
        conn.execute("BEGIN TRANSACTION;")
        for idx, osm_node in enumerate(in_data["elements"]):
            node_counter = idx
            if osm_node.get("type") == "node":
                parse_osm_node(conn, osm_node)

            if osm_node.get("type") == "way" and osm_node.get("nodes") != "None":
                parse_osm_way(conn, osm_node)
                # we only store the "<way>" id, since "<way>" is a set of "nodes"
                osm_filter_list.append(osm_node["id"])
                if osm_node.get("tags") is not None:
                    osm_node_id_tags[osm_node["id"]] = osm_node.get("tags")

            if idx % 1000 == 0:  # Commit every 1000 rows
                conn.commit()
                conn.execute("BEGIN TRANSACTION;")  # Start new transaction after we commited
    except Error as err:
        print('Error writing to SQLite: {err}')
    finally:
        conn.commit()

    print(f">> Processed {node_counter} nodes into rows.\n")

    return osm_filter_list


def process_osm_building_nodes(db, in_dc_config: dict, main_osm_id_list: list):
    way_counter = len(main_osm_id_list)
    # Step 2 - Create indexes after we parsed all data for better query performance
    post_overpass_index_creation(db)

    # Step 3 - Prepare custom WaveFront obj files before loading them into blender
    if db:
        flag_sqlite_support_math_functions = True
        if in_dc_config.get(CONFIG_SQLITE_SUPPORT_MATH) is not None:
            flag_sqlite_support_math_functions = in_dc_config.get(CONFIG_SQLITE_SUPPORT_MATH)

        # G_PREPARED_FILES_TO_PROCESS = 0

        # flag_sqlite_support_math_functions is for windows
        i_processed_files, i_skipped_files = parse_osm_to_wavefront_obj(conn=db, in_dc_config=in_dc_config
                                                                        , in_building_id_list=main_osm_id_list
                                                                        ,
                                                                        in_b_sqlite_supports_math=flag_sqlite_support_math_functions)

        print(f"\n>> OBJ_FILES Prepared: [{i_processed_files}|{i_processed_files + i_skipped_files}] files. "
              f"Skipped: [{i_skipped_files}].<<\n")  # v1.1

        # Step 4 - Call Blender to create and export the WaveFront file to X-Plane OBJ8 file.
        files_processed = 0
        if in_dc_config.get(CONFIG_USE_SQLITE_FLOW, False):
            files_processed = call_blender_v2(in_dc_config=in_dc_config,
                                              conn=db)  # sqlite flow code, "use_sqlite_flow=true". Slower.
        else:
            files_processed = call_blender_v1(in_dc_config=in_dc_config,
                                              conn=db)  # Recommended # v1.1 added DB connection

        # Step 5 - Prepare DSF info file to manually load into WED
        msg = ""
        if in_dc_config.get(CONFIG_USE_SQLITE_FLOW, False):
            # sqlite flow code, "use_sqlite_flow=true"
            create_dsf_text_file_with_all_the_osm_objects_and_copy_to_destination_lib_v2(conn=db,
                                                                                         in_dc_config=in_dc_config)
        else:
            msg = create_dsf_text_file_with_all_the_osm_objects_and_copy_to_destination_lib_v1(
                in_dc_config=in_dc_config)

        # General message
        print("""\nIf you would like to change the textures to "DDS" from "PNG", you should do the following:
        1. Convert the image to a DDS file using DDSTool application:
           "./DDSTool  --png2dxt3 --std_mips texture_2K.png texture_2K.dds"

        2. Modify all ".obj" files and rename the textures files with ".dds" extension.
           The command below modified all "*.obj" files in current and sub folders:
           "find ./ -type f -name "*.obj" -exec sed -i 's/.png/.dds/gI' {} \\;"
        """)

        print("\n<---- --------------------------- ---->\n")

        # Processed final statistics messages
        print(f"\n>> Found: {way_counter} way_id that represent buildings.<<")
        print(
            f">> OBJ_FILES Prepared: [{i_processed_files}/{i_processed_files + i_skipped_files}] files. Pre-Processed Skipped: [{i_skipped_files}].<<")  # v1.1
        print(f">> Blender Processed: {files_processed} files.<<")

        if msg != "":
            print(f'>> DSF Message: {msg!r}')


def call_overpass (bbox_coord: str, in_dc_config: dict = dict, in_overpass_json_file_name: str = ''):
    # initialize if to use overpass or local cached result
    b_use_overpass = True if bbox_coord != '' and in_overpass_json_file_name == '' else False
    b_fetch_data_from_overpass_was_successful = False
    data = {}

    # Default filter: retrieve buildings within the specified bounding box
    overpass_query = f"""
        [out:json];
        way ["building"] ({bbox_coord});
        (._;>;);
        out body;
        >;
    """

    overpass_query = in_dc_config.get(CONFIG_OBJ_FILTER, overpass_query) \
                     if in_dc_config.get(CONFIG_MODE, "") in ["", OPT_MODE_OBJ] else in_dc_config.get( CONFIG_HELIPAD_FILTER, "")
    # replace "{{bbox}}"
    overpass_query = overpass_query.replace("{{bbox}}", bbox_coord)

    if overpass_query == "":
        print('Error in "fetch_buildings_in_bbox_and_write_to_db". Overpass query is empty. Check config.json file')
        sys.exit()

    print(f'Overpass Query: {overpass_query}')  # debug

    # Send the query to the Overpass API or load from the cached JSON file
    try:
        if b_use_overpass:
            print('Calling Overpass, please wat...')  # debug
            # Fetch information from overpass
            response = requests.get(url=in_dc_config[CONFIG_OVERPASS_URL], params={"data": overpass_query},
                                    verify=False, timeout=in_dc_config.get(CONFIG_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT))  # default 30 seconds

            print(f"Response status: {response.status_code}")
            if response.ok:
                data = response.json()
                # write the response to local file
                try:
                    with open('overpass.json', 'w', encoding='utf8') as overpass_file:
                        json.dump(data, overpass_file, indent=4)
                except Exception as e:
                    print(f'failed writing the Overpass json respond.\n{e}')

                b_fetch_data_from_overpass_was_successful = True

        elif in_overpass_json_file_name != '':
            print(f'Using cached file: {in_overpass_json_file_name!r}, please wait...')  # debug
            with open(file=in_overpass_json_file_name, mode='r', encoding='utf8') as json_file:
                data = json.load(json_file)
                b_fetch_data_from_overpass_was_successful = True
        else:
            print('Check your config file for missing "overpass bbox", "json" or "debug" way_id.\n'
'Do you want to try overpass data instead ? Consider defining the {CONFIG_OSM_BBOX!r}. ')
            sys.exit()

    except HTTPError as http_err:
        print(f"HTTP error occurred:\n{http_err}\n")
        sys.exit()
    except Exception as err:
        print(f"Other error occurred:\n{err}\n")
        sys.exit()

    return b_fetch_data_from_overpass_was_successful, data


def fetch_osm_data_in_bbox_and_call_task_by_mode_value(db, bbox_coord: str, in_dc_config: dict = dict,
                                                       in_overpass_json_file_name: str = ''):
    # initialize if to use overpass or local cached result
    b_use_overpass = True if bbox_coord != '' and in_overpass_json_file_name == '' else False

    b_fetch_data_from_overpass_was_successful = False
    osm_filter_list = []  # return array of <way> ids
    osm_node_id_tags = {}  # dictionary of way_id and sub dictionary of {tags} = { way_id, {tags}}
    data = {}

    start_fetch_time = time.time()  # v1.1

    b_fetch_data_from_overpass_was_successful, data = call_overpass(bbox_coord=bbox_coord, in_dc_config=in_dc_config, in_overpass_json_file_name=in_overpass_json_file_name)

    if b_fetch_data_from_overpass_was_successful:
        if in_dc_config.get(CONFIG_MODE, "") == OPT_MODE_OBJ:
            ## Only now we initialize the database
            db = initialize_database ( in_dc_config=in_dc_config)
            osm_filter_list = parse_osm_building_nodes(conn=db, in_dc_config=in_dc_config, in_data=data)
            process_osm_building_nodes(db=db, in_dc_config=in_dc_config, main_osm_id_list=osm_filter_list)
        elif in_dc_config.get(CONFIG_MODE, "") == OPT_MODE_HELIPAD:
            parse_osm_helipad_nodes(in_dc_config=in_dc_config, in_data=data)
        else:
            print("Incorrect Mode found, aborting...")
            sys.exit()

    end_fetch_time = time.time()
    elapsed_fetch_time = end_fetch_time - start_fetch_time
    print(f"Fetched time in seconds: {elapsed_fetch_time:.6f}\n=========================\n")

    return osm_filter_list


def calculate_new_coordinates(start_x: float, start_y: float, distance_meters: float, bearing_degrees: int):
    """
  Calculate position of a vertex on a 2D plane
  """

    # Convert bearing from degrees to radians
    bearing_radians = math.radians(bearing_degrees)

    # Calculate the change in X and Y coordinates
    delta_x = distance_meters * math.cos(bearing_radians)
    delta_y = distance_meters * math.sin(bearing_radians)

    # Calculate the new coordinates
    new_x = start_x + delta_x
    new_y = start_y + delta_y

    return new_x, new_y


def fetch_osm_info_from_db(conn, binds: list = None, in_b_sqlite_supports_math: bool = True):
    if binds is None:
        binds = []

    if in_b_sqlite_supports_math:
        stmt = """select v2.seq, v2.way_id, v2.node_id, lat, lon, mt_distance
     , sum(mt_distance) over (partition by way_id ) as perimeter
     , DEGREES(atan2(sin(delta2) * cos(teta2), (cos(teta1) * sin(teta2) - sin(teta1) * cos(teta2) * cos(delta2) ) ) ) as degrees
     , ABS((DEGREES(atan2(sin(delta2) * cos(teta2), (cos(teta1) * sin(teta2) - sin(teta1) * cos(teta2) * cos(delta2) ) ) ) + 360.0 ) % 360) as degrees_round
     , max(v2.seq) over (partition by v2.way_id ) as max_seq

FROM
(
select v1.*
     , SQRT( POW(6371.0 * ABS(RADIANS(v1.lat) - RADIANS(v1.lead_lat)), 2) + POW( (6371.0 * COS(RADIANS(0.0)) * ABS(RADIANS(v1.lon) - RADIANS(v1.lead_lon))), 2 ) ) * 1000.0 mt_distance
     , RADIANS (v1.lat) as teta1
     , RADIANS (v1.lead_lat) as teta2
     , RADIANS (v1.lead_lon - v1.lon) as delta2
     , atan2(sin(v1.lead_lon - v1.lon) * cos(v1.lead_lat), cos(v1.lat) * sin(v1.lead_lat) - sin(v1.lat) * cos(v1.lead_lat) * cos( v1.lead_lon - v1.lon)) as bearing_cp

from (
select w.seq, w.way_id, n.node_id, n.lat, n.lon
               , lead (n.lat) over (partition by w.way_id order by seq) as lead_lat, lead (n.lon) over (partition by w.way_id order by seq) as lead_lon
               , lag (n.lat) over (partition by w.way_id order by seq) as lag_lat, lag (n.lon) over (partition by w.way_id order by seq) as lag_lon
from ways w
INNER JOIN nodes n
ON w.node_id = n.node_id
WHERE w.way_id = ?
) v1
) v2
order by v2.way_id, v2.seq
"""
    else:
        stmt = '''select w.seq, w.way_id, n.node_id, n.lat, n.lon
               , lead (n.lat) over (partition by w.way_id order by seq) as lead_lat, lead (n.lon) over (partition by w.way_id order by seq) as lead_lon
               , lag (n.lat) over (partition by w.way_id order by seq) as lag_lat, lag (n.lon) over (partition by w.way_id order by seq) as lag_lon
               , max(w.seq) over (partition by w.way_id ) as max_seq
from ways w
INNER JOIN nodes n
ON w.node_id = n.node_id
WHERE w.way_id = ?
    '''

    rows = exec_query_stmt(conn, stmt, binds, True)

    # Convert to python mutable dictionary since sqlite3.row is read-only
    dc_rows = {}  # [indx, {}]
    for indx, row in list(enumerate(rows)):
        keys = row.keys()
        dc_row = {}
        for key in keys:
            dc_row[key] = row[key]
        dc_rows[indx + 1] = dc_row

    if in_b_sqlite_supports_math:
        return dc_rows

    # Loop over all rows and manually calculate the "math" portion part
    perimeter = 0.0  # the same for all rows in specific way_id group
    for indx, row in dc_rows.items():  # calculate bearing, teta, delta1, delta2 and distance
        #  We will manually calculate the following information for sqlite binaries that were not built with "math" support.
        #      , sum(mt_distance) over (partition by way_id ) as perimeter
        #      , SQRT( POW(6371.0 * ABS(RADIANS(v1.lat) - RADIANS(v1.lead_lat)), 2) + POW( (6371.0 * COS(RADIANS(0.0)) * ABS(RADIANS(v1.lon) - RADIANS(v1.lead_lon))), 2 ) ) * 1000.0 mt_distance
        #      , RADIANS (v1.lat) as teta1
        #      , RADIANS (v1.lead_lat) as teta2
        #      , RADIANS (v1.lead_lon - v1.lon) as delta2

        earth_circumference_in_meters = 6371.0 * 1000.0

        if row.get(K_LEAD_LAT is None or row.get(K_LEAD_LAT) is None):
            row[K_MT_DISTANCE] = None
            row[K_DEGREES_ROUND] = None
            continue

        mt_distance = math.sqrt(math.pow(
            earth_circumference_in_meters * math.fabs(math.radians(row[K_LAT]) - math.radians(row[K_LEAD_LAT])),
            2) + math.pow((earth_circumference_in_meters * math.cos(math.radians(0.0)) * math.fabs(
            math.radians(row[K_LON]) - math.radians(row[K_LEAD_LON]))), 2))
        teta1 = math.radians(row[K_LAT])
        teta2 = math.radians(row[K_LEAD_LAT])
        delta2 = math.radians(row[K_LEAD_LON] - row[K_LON])

        row[K_MT_DISTANCE] = mt_distance
        row[K_TETA1] = teta1
        row[K_TETA2] = teta2
        row[K_DELTA2] = delta2

        if mt_distance is not None:
            perimeter += mt_distance

        # ABS((DEGREES(atan2(sin(delta2) * cos(teta2), (cos(teta1) * sin(teta2) - sin(teta1) * cos(teta2) * cos(delta2) ) ) ) + 360.0 ) % 360) as degrees_round
        if mt_distance is None or teta1 is None or teta2 is None or delta2 is None:
            row[K_DEGREES_ROUND] = -1.0
        else:
            row[K_DEGREES_ROUND] = math.fabs((math.degrees(math.atan2(math.sin(delta2) * math.cos(teta2), (
                    math.cos(teta1) * math.sin(teta2) - math.sin(teta1) * math.cos(teta2) * math.cos(
                delta2)))) + 360.0) % 360)

    # set perimeter into all dc_rows
    for indx, row in dc_rows.items():
        row[K_PERIMETER] = perimeter

    return dc_rows


def parse_osm_to_wavefront_obj(conn, in_dc_config: dict, in_building_id_list: list,
                               in_b_sqlite_supports_math: bool = True):
    global G_SKIPPED_FILES
    global G_PREPARED_FILES_TO_PROCESS
    global CONF_OUTPUT_OBJ_FILES
    global CONF_OUTPUT_OBJ_RESUME_FILES_NAME
    # global G_OUTPUT_OBJ_FILES_NAME
    # global G_OUTPUT_OBJ_RESUME_FILES_NAME

    # https://developer.x-plane.com/article/obj8-file-format-specification/
    # COORDINATE SYSTEM AND GEOMETRY
    # OBJ8 models are specified in meters.
    # In their native orientation:
    #     the positive Y axis points up,
    #     the positive X axis points east, and
    #     the positive Z axis points south.
    #     (This is a right-handed coordinate system.)
    #     The point 0,0,0 is a point on the ground where the object has been placed in x-plane scenery.
    #     The X-Plane scenery file referencing the object may rotate the object clockwise around the Y axis.

    # clear obj_files.txt file
    with open(file=in_dc_config.get(CONF_OUTPUT_OBJ_FILES, f'{CONF_OUTPUT_OBJ_FILES}.txt'), mode='w', encoding='utf8'):
        pass

    with open(file=in_dc_config.get(CONF_OUTPUT_OBJ_RESUME_FILES_NAME, f'{CONF_OUTPUT_OBJ_RESUME_FILES_NAME}.txt'),
              mode="w", encoding="utf8"):
        pass

    i_limit = 0
    i_actual_processed = 0  # v1.1
    i_skipped_files = 0  # v1.1
    G_PREPARED_FILES_TO_PROCESS = 0
    G_SKIPPED_FILES = 0

    for way_id in in_building_id_list:
        i_limit += 1
        # v1.2 fixed limiting tests.
        if i_limit > in_dc_config.get(CONFIG_LIMIT, DEFAULT_LIMIT_FILES):
            return i_actual_processed, i_skipped_files  # Exit the loop # v1.1 added processed + skipped files

        if (in_dc_config.get(CONFIG_FILTER_OUT_EVERY_NTH_MESH) is not None
                and i_limit % int(in_dc_config.get(CONFIG_FILTER_OUT_EVERY_NTH_MESH)) == 0):
            print(f'Filter out by rule - way id: {way_id}')
            G_SKIPPED_FILES += 1
            i_skipped_files += 1
            continue

        binds = [way_id]
        dc_rows = fetch_osm_info_from_db(conn, binds, in_b_sqlite_supports_math)

        print(f'Fetched: {len(dc_rows)} rows.')  # debug

        if len(dc_rows) == 0:
            print(f'There are no rows corresponding to the way id: {way_id}. Aborting script.')
            sys.exit(-1)

        # Loop over all rows and create the base of the OBJ mesh
        vt_obj_wavefront = []  # Initialize with 0,0 coordinates
        x = y = z = last_x = last_z = 0.0  # removed last_y
        mx_vert_length = 0.0  # will hold the longest row[K_MT_DISTANCE]
        mesh_rotation = 0.0

        # f_mesh_perimeter = 0.0
        last_row = None
        for idx, (row_no, row) in enumerate(dc_rows.items()):

            y = 0  # currently y always equal to zero, since we are drawing a plane
            if (row[K_MT_DISTANCE] is not None) and mx_vert_length < row[K_MT_DISTANCE]:
                mx_vert_length = row[K_MT_DISTANCE]

            # calculate new position based on previous coordinates, distance and bearing
            if idx > 0 and row[K_SEQ] < (row[K_MAX_SEQ] - 1):  # We calculate rows 1..(N-1)
                # In X-Plane X=east/west, Z=North South
                try:
                    x, z = calculate_new_coordinates(last_x, last_z, row[K_MT_DISTANCE], row[K_DEGREES_ROUND])
                    if row_no == 2 and idx == 1:
                        mesh_rotation = row[K_DEGREES_ROUND]
                except Error as e:
                    print(f"{e}\n\tFor row: {idx}")
                    continue
            elif idx == 0:
                vt_obj_wavefront.append([x, y, z])  # store position array [0,0,0]
                x, z = calculate_new_coordinates(last_x, last_z, row[K_MT_DISTANCE], row[K_DEGREES_ROUND])
            elif row[K_SEQ] == row[K_MAX_SEQ]:
                # We inject to last "row" the mesh rotation for future use
                row[K_ROTATION] = mesh_rotation
                last_row = copy.deepcopy(row)
                break  # exit loop without handling closing vertex
            else:
                last_row = copy.deepcopy(row)
                continue  # We should never reach this line of code.

            vt_obj_wavefront.append([x, y, z])  # store in array
            last_x = x
            # last_y = y
            last_z = z

        ###############################
        # Filter by perimeter or Wall Length
        ###############################

        filter_out_obj_with_perimeter_greater_than = in_dc_config.get(CONFIG_FILTER_OUT_OBJ_WITH_PERIMETER_GREATER_THAN,
                                                                      0.0)
        filter_out_obj_with_perimeter_less_than = in_dc_config.get(CONFIG_FILTER_OUT_OBJ_WITH_PERIMETER_LESS_THAN, 0.0)
        filter_in_obj_with_perimeter_between_lst = in_dc_config.get(CONFIG_FILTER_IN_OBJ_WITH_PERIMETER_BETWEEN, [])

        print(f'{way_id=!r}, {last_row[K_PERIMETER]=!r}')  # v1.2 perimeter info

        # Filter out by wall length
        if mx_vert_length > in_dc_config.get(CONFIG_MAX_WALL_LENGTH, 0.0) > 0.0:
            i_skipped_files += 1
            print(
                f"Way: {way_id} has a wall longer than {in_dc_config.get(CONFIG_MAX_WALL_LENGTH, 0.0)} meters. Skipping...")
            continue

        # Filter out objects with perimeter larger than
        if last_row[K_PERIMETER] > filter_out_obj_with_perimeter_greater_than > 0.0:
            i_skipped_files += 1
            print(
                f"\nWay: {way_id} has a perimeter longer than {filter_out_obj_with_perimeter_greater_than} meters. Perimeter length: {last_row[K_PERIMETER]}. Skipping...\n")
            continue

        # Filter out objects with perimeter less than
        if last_row[K_PERIMETER] < filter_out_obj_with_perimeter_less_than > 0.0:
            i_skipped_files += 1
            print(
                f'''\nWay: {way_id} has a perimeter less than {filter_out_obj_with_perimeter_less_than} meters. 
                Perimeter length: {last_row[K_PERIMETER]}. Skipping...\n '''
            )
            continue

        # Filter in objects with perimeter between
        if isinstance(filter_in_obj_with_perimeter_between_lst, list) and len(
                filter_in_obj_with_perimeter_between_lst) > 1:
            # check if the mesh perimeter is outside the "filter in" values.
            # Check if the shortest allowed length is bigger than the perimeter
            # or the biggest allowed length is shorter than the perimeter.
            if filter_in_obj_with_perimeter_between_lst[0] > last_row[K_PERIMETER] or last_row[K_PERIMETER] > \
                    filter_in_obj_with_perimeter_between_lst[1]:
                i_skipped_files += 1
                print(
                    f'''\nWay: {way_id} has a perimeter not in the filter range: {filter_in_obj_with_perimeter_between_lst!r}  
                    Perimeter length: {last_row[K_PERIMETER]}. Skipping...\n '''
                )
                continue

        # We assume that all arrays represents a cube, so we need to add the elevation coordinates

        vt_obj_wavefront.reverse()
        vt_obj_wavefront_elev = copy.deepcopy(vt_obj_wavefront)

        #################
        # Tentative height decision, not using OSM Metadata
        #################
        f_height = 2.5

        # Decide height by longest edge. units: meters
        if mx_vert_length > 20:
            f_height = 9.0
        elif mx_vert_length > 12:
            f_height = 6.0
        elif mx_vert_length > 8:
            f_height = 3.5

        # Decide height using perimeter information
        if last_row[K_PERIMETER] > 150.0:
            f_height = 9.0
        elif last_row[K_PERIMETER] > 80:
            f_height = 6.0

        # v1.1 gather way_id metadata information to send to Blender
        s_default_where_const = "and ( k like 'build%' or k = 'amenity' or k='height' )"
        stmt = f'select k, v from ways_meta where way_id=? {dc_config.get(CONFIG_QUERY_META_TEXT, s_default_where_const)}'
        rows = exec_query_stmt(conn, stmt, binds, True)
        dc_way_meta = {}
        # print(f'rows type:{type(rows)}')

        # TODO: Re-write this code to be more pythonic
        for indx, row in list(enumerate(rows)):
            keys_list = row.keys()
            i = 1
            key = ""
            for k in keys_list:
                if i == 1:
                    key = row[k]
                    dc_way_meta[key] = ""
                    i += 1
                elif i == 2:
                    dc_way_meta[key] = row[k]
                    i += 1
                    break
                else:
                    break

        in_dc_config["way_meta"] = dc_way_meta
        print(f'{dc_way_meta}\n')

        list_height_keys = in_dc_config.get(CONFIG_HEIGHT_KEYS_LIST, [])
        building_height = 0.0
        if isinstance(list_height_keys, list):
            for l_key in list_height_keys:
                if l_key in dc_way_meta:
                    if is_number(dc_way_meta[l_key]):
                        building_height = float(dc_way_meta[l_key])
                    else:
                        flag_parsed, num_parsed_list = parse_feet_inches(dc_way_meta[l_key])
                        if flag_parsed:
                            building_height = num_parsed_list[0] * 0.3048  # convert to meters
                            break  # exit loop
                        else:
                            building_height = 0.0

            print(f'Metadata height: {building_height=}')

        if building_height > 0.0:
            f_height = building_height

        # v1.2 Added support of level key list. There might be other keys that represent levels.
        # First found, first served.
        building_levels = 0
        list_of_level_keys = in_dc_config.get('level_keys_list', [])
        if not isinstance(list_of_level_keys, list):
            list_of_level_keys = []
        for key in list_of_level_keys:
            if dc_way_meta.get(key, None) is not None:
                building_levels = int(dc_way_meta.get(key, 1))
                break

        # The next logic is to make sure that the value is valid, or
        # we fall back to the default osm key metadata for levels.
        building_levels = building_levels if building_levels > 0 else int(dc_way_meta.get("building:levels", 1))

        # v1.1 Force building level rules
        if building_levels > 1:
            f_height = building_levels * 3.0  # Default floor height is 3 meters
        else:
            building_levels = 1  # make sure never Zero

        print(f'Final Height: {f_height=}, {building_height=}, {building_levels=}')  # debug
        # end v1.1 height information

        # create a list of levels: [vt_obj_wavefront_elev, vt_obj_wavefront_elev,vt_obj_wavefront_elev]
        # Each element represents a building level
        # Modify height
        for vt_array in vt_obj_wavefront_elev:
            # validate we have a tuple
            if len(vt_array) > 2:
                vt_array[1] = f_height / building_levels

        # make a copy of the top face * number of levels
        list_of_vt_obj_wavefront_elev_levels = []
        for lvl in range(building_levels):
            list_of_vt_obj_wavefront_elev_levels.append(copy.deepcopy(vt_obj_wavefront_elev))

        v_processed = write_cube_from_osm_to_wavefront_format(conn, way_id, in_dc_config, building_levels, f_height,
                                                              vt_obj_wavefront, vt_obj_wavefront_elev, last_row)
        G_PREPARED_FILES_TO_PROCESS += v_processed
        i_actual_processed += v_processed
        i_skipped_files += 1 if v_processed == 0 else 0  # add 1 only if v_processed is zero

        # debug_limit = in_dc_config.get(CONFIG_LIMIT, DEFAULT_LIMIT_FILES)
        if i_limit + 1 > in_dc_config.get(CONFIG_LIMIT, DEFAULT_LIMIT_FILES):
            return i_actual_processed, i_skipped_files  # Exit the loop # v1.1 added processed + skipped files

    return i_actual_processed, i_skipped_files


def write_cube_from_osm_to_wavefront_format(conn, way_id: int, in_dc_config: dict, in_building_levels: int,
                                            in_suggested_height: float, vt_arrays=None, vt_arrays_elev=None, row=None):
    """ Write the base cube to an "{}_osm.obj" file to use later with blender. """
    global CONF_OUTPUT_OBJ_FILES
    global CONF_OUTPUT_OBJ_RESUME_FILES_NAME

    if vt_arrays is None:
        vt_arrays = []
    if vt_arrays_elev is None:
        vt_arrays_elev = []
    if row is None:
        row = {}

    # v1.1 Prepare all vt levels as list[list...]
    if in_building_levels < 1:
        in_building_levels = 1

    list_all_levels = [vt_arrays]
    list_all_levels_index = []
    for lvl in range(in_building_levels):
        list_all_levels.append(copy.deepcopy(vt_arrays_elev))  # Adding elevated levels

    i_counter = 1
    for indx, vt_list in enumerate(list_all_levels):
        vt_indx = []
        for vt_point in vt_list:
            vt_point[1] = indx * (in_suggested_height / in_building_levels)
            vt_indx.append(i_counter)
            i_counter += 1
        # Store index
        list_all_levels_index.append(copy.deepcopy(vt_indx))
        vt_indx.clear()

    # print(f'{list_all_levels=}')  # debug
    # print(f'{list_all_levels_index=}')  # debug
    # v1.1 end

    ####################
    # open output file #
    ####################
    # dir_path = os.path.dirname(os.path.realpath(__file__))
    #
    # dc_config[CONFIG_WORK_FOLDER_IS_ABSOLUTE_PATH] = False  # initialized
    #
    # work_path = dc_config.get(CONFIG_SCRIPT_WORK_FOLDER, os.path.join(dir_path, "out") )
    # out_path = work_path
    # if Path(work_path).is_absolute():
    #     out_path = work_path
    #     dc_config[CONFIG_WORK_FOLDER_IS_ABSOLUTE_PATH] = True
    # if dc_config.get(CONFIG_SCRIPT_WORK_FOLDER, '') != '':
    #     work_path = dc_config.get(CONFIG_SCRIPT_WORK_FOLDER)
    #
    #     # construct final output folder based on if configuration is absolute or relative
    #     if Path(work_path).is_absolute():
    #         out_path = work_path
    #         dc_config[CONFIG_WORK_FOLDER_IS_ABSOLUTE_PATH] = True
    #     else:
    #         out_path = os.path.join(dir_path, work_path)
    # else:
    #     out_path = os.path.join(dir_path, work_path)
    # dc_config[CONFIG_WORK_FOLDER] = out_path

    out_path = dc_config.get(CONFIG_WORK_FOLDER, "out")

    # Create the working folder "out" if it is not available
    if not os.path.isdir(out_path):
        try:
            os.mkdir(out_path)
        except OSError as ose:
            print(f'Failed to create "out" folder.\n{ose}')
            sys.exit(1)

    s_lat_lon = f'{row[K_LAT]}_{row[K_LON]}'

    # define the base output file name
    base_file_name = f'xx_({s_lat_lon})_{way_id}'
    # base_file_name = f'xx_{s_lat_lon}_{way_id}'  # v25.05.1 "[]" instead of "()" in the hope to solve the file naming issues is io.path.isFile()
    # "{dir_path}/out/{base_file_name}_osm.obj" # will be used for import into blender
    output_file = os.path.join(out_path, base_file_name) + "_osm.obj"
    output_file_obj8 = os.path.join(out_path, base_file_name) + "_osm_obj8.obj"  # v1.1

    # Check skip rules: if file exists and larger than 500 bytes then skip.
    if check_skip_and_resume_settings(in_dc_config=in_dc_config, in_resume_lvl_needed=5, in_output_file=output_file
            , in_output_file_obj8=output_file_obj8
            , lon_lat_way_id_s=f'{row[K_LON]} {row[K_LAT]} 0.00|{way_id}'
                                      ):
        return 0

    ########
    # Header
    s_header = f"""# $0 {G_VERSION}
    #Written by Saar
    """
    s_output_object = "o cube\n"  # type of vertex object: plane, cube etc

    with open(file=output_file, mode="w", encoding="utf8") as text_file:
        text_file.write(s_header)
        # text_file.write(sMtllib)
        text_file.write(s_output_object)

        # v1.1 Write vertex (v) from array. Write from all lists
        for level in list_all_levels:
            for vt_row in level:
                text_file.write("v")
                for vt in vt_row:
                    text_file.write(' {:.2f}'.format(vt))
                text_file.write("\n")

        i_counter = 0
        s_faces = ""
        i_index_normal = 1

        # v1.1
        # Loop over all levels lists and prepare the faces
        dc_faces_list = {}
        for indx_list_i in range(len(list_all_levels_index)):
            current_list = list_all_levels_index[indx_list_i]

            # The following code will wrap around to the first list after the last list.
            # We will stop once this occurs
            next_list = list_all_levels_index[(indx_list_i + 1) % len(list_all_levels_index)]

            # exit if we wrapped around, if we reached the last index, we don't want to cycle
            if indx_list_i + 1 == len(list_all_levels_index):
                break

            for indx in range(len(current_list)):
                i_counter += 1
                if indx + 1 < len(current_list):
                    # vt base1, vt base2, vt base1'(elev), vt base2'(elev)
                    s_faces = f"{current_list[indx]}//{i_index_normal} {current_list[indx + 1]}//{i_index_normal} {next_list[indx + 1]}//{i_index_normal} {next_list[indx]}//{i_index_normal}"
                else:
                    s_faces = f"{current_list[indx]}//{i_index_normal} {current_list[0]}//{i_index_normal} {next_list[0]}//{i_index_normal} {next_list[indx]}//{i_index_normal}"

                dc_faces_list[i_index_normal] = s_faces
                i_index_normal += 1

        ########################
        # Add Bottom and Top faces
        ########################
        # Add Bottom face
        s_faces = ""
        for indx in range(len(list_all_levels_index[0])):
            s_faces += f"{list_all_levels_index[0][indx]}//{i_index_normal} "

        dc_faces_list[i_index_normal] = s_faces

        # Add Top face
        i_index_normal += 1
        s_faces = ""

        top_level_list = list_all_levels_index[-1]  # DEBUG return the last list in the array
        for indx, val_index in enumerate(list_all_levels_index[-1]):
            s_faces += f"{val_index}//{i_index_normal} "

        dc_faces_list[i_index_normal] = s_faces

        ########################
        # Write Vertex Textures (vt)
        ########################
        # Write s
        text_file.write("s 0\n")
        # Write material name: usemtl blue
        text_file.write("usemtl blue\n")
        ########################

        # Write Faces
        for indx, s_face in dc_faces_list.items():
            text_file.write(f"f {s_face}\n")

        #################################################
        # Write the "obj" file into the "G_OUTPUT_OBJ_FILES_NAME" or the database
        if dc_config.get(CONFIG_USE_SQLITE_FLOW, False):
            conn.execute("BEGIN TRANSACTION;")
            binds = [way_id, row[K_LAT], row[K_LON], output_file, row[K_ROTATION]]
            stmt = f"insert into {G_OBJ8_DATA_TABLE} (way_id, lat, lon, file_name_osm, rotation) values (?,?,?,?,?)"  # initialize the row in obj8_data table
            exec_stmt(conn, stmt, binds)
            binds.clear()
            conn.execute("END TRANSACTION;")

        # generate_obj_file_log = os.path.join(in_dc_config.get(CONFIG_LOG_FOLDER), in_dc_config.get(CONF_OUTPUT_OBJ_FILES))
        # with open(generate_obj_file_log, 'a', encoding='utf8') as file:
        with open(f"{in_dc_config[CONF_OUTPUT_OBJ_FILES]}", 'a', encoding='utf8') as file:
            # Write the ".obj" file name, position (lon lat), heading (0.0) and way_id for future use.
            file.write(f'{output_file}|{row[K_LON]} {row[K_LAT]} 0.00|{way_id}\n')

        return 1


def call_blender_v1(in_dc_config: dict, conn):
    # # Calculate Vertex Normal Using Blender + create OBJ8 file ###
    # /mnt/virtual/tools/blender-3.6.10-linux-x64/blender
    # ~/programming/git/osm_to_xplane/blender/empty.blend
    # --background
    # --python /home/xplane/programming/git/osm_to_xplane/blender-addon/run_ImportAndFlipNormals.py -- "/home/xplane/programming/git/osm_to_xplane/out/xx_690633916_cube.obj"

    # s_default_where_const = "and ( k like 'build%' or k = 'amenity' )"
    global CONF_OUTPUT_OBJ_FILES
    global CONF_OUTPUT_OSM_TO_OBJ_BLEND_LOG_FILENAME

    current_directory = os.getcwd()

    blender_bin = in_dc_config.get(CONFIG_BLENDER_BIN)  # "/mnt/virtual/tools/blender-3.6.10-linux-x64/blender"
    if os.path.isfile(blender_bin):
        print(f"{blender_bin} exists.")
    else:
        print(f"[Error] {blender_bin} does not exist or is not a regular file.")
        sys.exit(1)

    blend_file = f'{current_directory}/blender/empty.blend'
    custom_py_script = f'{current_directory}/blender/run_blender_script.py'

    blend_flags = " --background "
    py_flags = f"--python {custom_py_script} "

    i_processed = 0
    try:
        # logfile_name = f'osm_to_obj_blend_{in_dc_config.get(CONFIG_OSM_BBOX, '').replace(',', '_')}.log'
        logfile_name = in_dc_config.get(CONF_OUTPUT_OSM_TO_OBJ_BLEND_LOG_FILENAME)
        # Reset log file
        with open(file=logfile_name, mode='w', encoding='utf8'):
            pass

        # with open(file=G_OUTPUT_OBJ_FILES_NAME, mode='r', encoding='utf8') as file:
        with open(file=in_dc_config.get(CONF_OUTPUT_OBJ_FILES), mode='r', encoding='utf8') as file:
            while True:
                line = file.readline()
                if line == '':
                    break

                # Split each line information (file|coordination|way id)
                split_line_list = line.split("|")
                obj_file = split_line_list[0]  # Extract the file name
                working_way_id = split_line_list[2].strip()  # Extract the way_id  v1.1 added way_id to blender

                # Check resume rules: if file exists and larger than 500 bytes then skip.
                obj8_file_name = os.path.splitext(obj_file)[0] + "_obj8.obj"
                if check_skip_and_resume_settings(in_dc_config=in_dc_config, in_resume_lvl_needed=10,
                                                  in_output_file=obj_file
                        , in_output_file_obj8=obj8_file_name
                        , lon_lat_way_id_s=f'{split_line_list[1]}|{working_way_id}'
                                                  ):
                    continue

                # store way_id in dictionary
                in_dc_config["way_id"] = working_way_id  # v1.1 added way_id to dictionary, to use with Blender

                # v1.1 remove the query definition to resolve "blender" fail due to the "( or )" chars.
                if in_dc_config.get(CONFIG_QUERY_META_TEXT, None) is not None:
                    del (in_dc_config[CONFIG_QUERY_META_TEXT])

                dc_copy = copy.deepcopy(in_dc_config)
                dc_copy[CONFIG_OBJ_FILTER] = None
                dc_copy[CONFIG_HELIPAD_FILTER] = None

                py_env_flags = f'-- "{dc_copy}" "{obj_file}" '

                # os_command = f'GVFS_DISABLE_FUSE=1 "{blender_bin}" "{blend_file}" {blend_flags} {py_flags} {py_env_flags}'
                os_command = f'"{blender_bin}" "{blend_file}" {blend_flags} {py_flags} {py_env_flags}'
                i_processed += 1
                print(f"file: [{i_processed}/{G_PREPARED_FILES_TO_PROCESS}]: Blender: {obj_file}")
                print(f'{in_dc_config.get("way_meta")=}')  # debug

                try:
                    v1_start_time = time.time()

                    subprocess.check_call(os_command, shell=True)
                    v1_end_time = time.time()
                    v1_elapsed_time = v1_end_time - v1_start_time
                    print(
                        f"file: [{i_processed}/{G_PREPARED_FILES_TO_PROCESS}]: Processed in: {v1_elapsed_time:.6f} sec")
                except CalledProcessError as cpe:
                    print(f'\nFAIL Blender execution for {obj_file!r}\n{cpe}')
                    sys.exit(1)

    except OSError as ose:
        print(ose)

    print("\n<---- Finished Blender Processing ---->\n")
    return i_processed


def call_blender_v2(in_dc_config: dict, conn=object()):
    """

  Parameters
  ----------
  conn : SQLITE Connection,

  Returns
  -------
  i_processed : integer
      DESCRIPTION.
      :param conn:
      :param in_dc_config:

  """

    # global G_OUTPUT_OBJ_FILES_NAME
    global CONFIG_BLENDER_BIN
    # global dc_config

    # ## Calculate Vertex Normal Using Blender + create OBJ8 file
    # /mnt/virtual/tools/blender-3.6.10-linux-x64/blender
    # ~/programming/git/osm_to_xplane/blender/empty.blend
    # --background
    # --python /home/xplane/programming/git/osm_to_xplane/blender-addon/run_ImportAndFlipNormals.py -- "/home/xplane/programming/git/osm_to_xplane/out/xx_690633916_cube.obj"

    current_directory = os.getcwd()

    blender_bin = in_dc_config.get(CONFIG_BLENDER_BIN)  # "/mnt/virtual/tools/blender-3.6.10-linux-x64/blender"
    if os.path.isfile(blender_bin):
        print(f"{blender_bin} exists.")
    else:
        print(f"[Error] {blender_bin} does not exist or is not a regular file.")
        sys.exit(1)

    blend_file = f'{current_directory}/blender/empty.blend'
    custom_py_script = f'{current_directory}/blender/run_blender_script.py'

    blend_flags = " --background "
    py_flags = f"--python {custom_py_script} "

    i_processed = 0
    try:
        # Reset log file
        with open(file='osm_to_obj_blend.log', mode='w', encoding='utf8'):
            pass

        # fetch obj osm information from obj8_data table
        stmt = 'select way_id, lat, lon, file_name_osm from obj8_data'
        rows = exec_query_stmt(conn, stmt)

        # loop over all rows
        for row in rows:
            way_id = row[K_WAY_ID]
            obj_file = row[K_FILE_NAME_OSM]

            in_dc_config[K_WAY_ID] = way_id

            dc_copy = copy.deepcopy(in_dc_config)
            dc_copy[CONFIG_OBJ_FILTER] = ''
            dc_copy[CONFIG_HELIPAD_FILTER] = ''

            py_env_flags = f'-- "{dc_copy}" "{obj_file}" '

            os_command = f'"{blender_bin}" "{blend_file}" {blend_flags} {py_flags} {py_env_flags}'
            i_processed += 1
            print(f"file: [{i_processed}/{G_PREPARED_FILES_TO_PROCESS}]: Blender: {obj_file}")

            try:
                v2_start_time = time.time()
                subprocess.check_output(os_command, shell=True)
                v2_end_time = time.time()
                v2_elapsed_time = v2_end_time - v2_start_time
                print(
                    "file: [{}/{}]: Processed in: {:.6f} sec".format(i_processed, G_PREPARED_FILES_TO_PROCESS,
                                                                     v2_elapsed_time))

            except CalledProcessError as cpe:
                print(f"\nFAIL Blender execution for {obj_file!r}\n{cpe}")
                sys.exit(1)

    except OSError as ose:
        print(ose)

    print("\n<---\n")
    return i_processed


def create_dsf_text_file_with_all_the_osm_objects_and_copy_to_destination_lib_v1(in_dc_config: dict):
    """ Create the DSF file to use with WED """
    global CONF_OUTPUT_OBJ_FILES
    global CONF_OUTPUT_OBJ_RESUME_FILES_NAME

    # Get the scenery sub-folder to where to copy the obj8 files
    lib_relative_path = in_dc_config.get(CONFIG_LIB_RELATIVE_PATH, 'objects')

    # Check existence of target folder in config.json file. Skip this step if it is not.
    # if in_dc_config.get(CONFIG_ROOT_SCENERY_FOLDER_TO_COPY_OBJ8_FILES, '') == '' and in_dc_config.get(CONFIG_DEBUG_FORCE_DSF_CREATION, False) == False:
    if in_dc_config.get(CONFIG_ROOT_SCENERY_FOLDER_TO_COPY_OBJ8_FILES, '') == '':
        msg = 'Custom Scenery is not defined, will skip obj8 copy and DSF preparation file.'
        print(msg)  # debug
        return msg

    current_folder = os.getcwd()
    output_folder = current_folder
    if in_dc_config.get(CONFIG_OUTPUT_FOLDER_FOR_THE_DSF_TEXT, '') != '':
        output_folder = in_dc_config.get(CONFIG_OUTPUT_FOLDER_FOR_THE_DSF_TEXT)

    postfix = in_dc_config.get(CONFIG_OSM_BBOX, '').replace(',', '_')
    output_dsf_text_file_name = f'{DEFAULT_DSF_TEXT_OUTPUT_FILE_NAME}_{postfix}.txt'
    output_dsf_text = os.path.join(output_folder, output_dsf_text_file_name)

    # Prepare the DSF Text file
    # 1. Read line by line from CONF_OUTPUT_OBJ_FILES was G_OUTPUT_OBJ_FILES_NAME
    # 2. Extract and rename the base_file name and add "_obj8" to it. split[0]
    # 3. Add the prefix: "OBJECT_DEF objects/{file_name}.obj" to the "dsf_text,txt" file and store its index, start in 0
    # 4. Add in a List the "OBJECT" positioning location from the extracted line (split[1])
    ##
    try:
        # Truncate output file
        with open(file=output_dsf_text, mode='w', encoding='utf8'):
            pass

        # Copy template content into target file
        with open(DEFAULT_INPUT_DSF_TEMPLATE_FILE_NAME, 'r', encoding='utf8') as input_template:
            with open(output_dsf_text, 'w', encoding='utf8') as dsf_text_out:
                for line in input_template:
                    dsf_text_out.write(line)

        # Loop over obj_files.txt
        indx_file_counter = 0
        ls_object_position_list = []
        # ls_source_obj_files_to_read = [G_OUTPUT_OBJ_FILES_NAME, G_OUTPUT_OBJ_RESUME_FILES_NAME]
        ls_source_obj_files_to_read = [in_dc_config[CONF_OUTPUT_OBJ_FILES],
                                       in_dc_config[CONF_OUTPUT_OBJ_RESUME_FILES_NAME]]
        for source_file_enum, source_file in enumerate(
                ls_source_obj_files_to_read):  # loop start with "0" until "2" including

            with open(source_file, 'r', encoding='utf8') as in_file:
                for line in in_file:
                    list_data = line.split('|')  # split the pipe "|"
                    if len(list_data) > 1:
                        s_source_osm_file_to_copy = list_data[0]

                    if source_file_enum == 0:
                        file_name = os.path.basename(s_source_osm_file_to_copy)  # extract only file name
                        if file_name.endswith(".obj"):
                            insert_position = -4
                            s_target_file_name = f'{file_name[:insert_position]}_obj8{file_name[insert_position:]}'
                    else:
                        # final name ia already stored in resume file
                        s_target_file_name = os.path.basename(s_source_osm_file_to_copy)

                    # Get the scenery sub-folder to where to copy the obj8 files
                    lib_relative_path = in_dc_config.get(CONFIG_LIB_RELATIVE_PATH, 'objects')
                    s_path = os.path.join(in_dc_config.get(CONFIG_ROOT_SCENERY_FOLDER_TO_COPY_OBJ8_FILES, ''),
                                          lib_relative_path)
                    s_source_obj8_file = os.path.join(in_dc_config.get(CONFIG_WORK_FOLDER), s_target_file_name)

                    # Check existence of target folders and files
                    if not os.path.isdir(s_path):
                        print(
                            f'{source_file_enum}: Destination library is invalid.\npath: {s_path!r}.\n\tSkipping OBJ8 copy task.')
                        continue
                    if not os.path.isfile(s_source_obj8_file):
                        print(
                            f'{source_file_enum}: Source file is invalid: {s_source_obj8_file!r}. Skipping OBJ8 copy task.')
                        continue

                    # Copy to library using simple stream
                    try:
                        with open(s_source_obj8_file, 'r', encoding='utf8') as obj8_in_file:
                            s_target_file = os.path.join(s_path, s_target_file_name)
                            with open(s_target_file, 'w', encoding='utf8') as obj8_out_file:
                                print(f"Copy: {s_target_file}")
                                for read_line in obj8_in_file:
                                    obj8_out_file.write(read_line)

                    except FileNotFoundError as ffe:
                        print(f'{__name__}: FileNotFoundError: {ffe}')
                        continue
                    except Exception as e:
                        print(f'{__name__}: Failed to write from file: {s_source_obj8_file}\nError: {e}')
                        continue

                    # Prepare and write to DSF2TEXT file only if we could copy the OBJ8 file
                    # and make sure that the "dsf_obj8.txt" path is unix based, meaning, folder separator = "/"
                    s_object_def = f'OBJECT_DEF {lib_relative_path.replace('\\', '/')}/{s_target_file_name}'
                    ls_object_position_list.append(f'OBJECT {indx_file_counter} {list_data[1]}\n')

                    with open(output_dsf_text, 'a', encoding='utf8') as dsf_text:
                        dsf_text.write(s_object_def + "\n")

                    indx_file_counter += 1

        # After the second LOOP we write to the position into the DSF.txt file
        # Write OBJECTS into the dsf_text, always come after the OBJECT_DEF, probably because of the indexing
        if len(ls_object_position_list) > 0:
            with open(output_dsf_text, 'a', encoding='utf8') as dsf_text:
                dsf_text.writelines(ls_object_position_list)

            print("\n<---\n")

            output_dsf_file = f'{output_dsf_text}.dsf'
            # Execute DSF2Text on the copied "dsf_obj8.txt" file
            # The output_folder is where we place the "dsf2txt.txt" file to convert to DSF
            if platform.system().lower() == 'windows':
                # For Windows OS, we will construct absolute paths
                dsf_tool_bin = '{}'.format(os.path.join(current_folder, output_folder, 'DSFTool.exe'))
                source_dsf_file = os.path.join(current_folder, output_dsf_text)
                os_command = 'type {} | {} -text2dsf - {}.dsf'.format(source_dsf_file, dsf_tool_bin,
                                                                      os.path.join(current_folder, output_dsf_text))

            else:
                dsf_tool_bin = os.path.join(output_folder, 'DSFTool')
                os_command = f'cat {output_dsf_text} | {dsf_tool_bin} -text2dsf - {output_dsf_file}'

            print(f"DSF2Text:\n{os_command}")

            try:
                result = subprocess.check_output(os_command, shell=True)
                print(f"\nDSFTool Result:\n{result}")

                if os.path.isfile(output_dsf_file):
                    try:
                        shutil.copy(output_dsf_file, in_dc_config.get(CONFIG_ROOT_SCENERY_FOLDER_TO_COPY_OBJ8_FILES))
                        print(
                            f'Copied dsf file: {output_dsf_file!r} to {in_dc_config.get(CONFIG_ROOT_SCENERY_FOLDER_TO_COPY_OBJ8_FILES)!r}')
                    except FileNotFoundError:
                        print(f"Error: Source file {output_dsf_file!r} not found.")
                    except PermissionError:
                        print(f"Error: Permission denied when trying to copy {output_dsf_file!r}.")
                    except Exception as e:
                        print(f"An unexpected error occurred: {e}")

            except subprocess.CalledProcessError as sub_process_err:
                print(sub_process_err)
                print(f'''
[Warning] Failed to execute: DSFTool.

Check if it is located in the same folder as the {output_dsf_text!r} file.
You can manually convert the {DEFAULT_DSF_TEXT_OUTPUT_FILE_NAME!r} to DSF using the DSFTool:
Linux:
> cat {DEFAULT_DSF_TEXT_OUTPUT_FILE_NAME} | DSFTool -text2dsf - output.dsf
Windows:
> type {DEFAULT_DSF_TEXT_OUTPUT_FILE_NAME} | .\\DSFTool.exe -text2dsf - output.dsf
    
    ''')

    except Exception as e:
        print(f"Fail to write to {output_dsf_text!r} file.\n{e}")
        return f'Fail to write to {output_dsf_text!r} file.\n{e}'
        # sys.exit(1)

    return ""


def create_dsf_text_file_with_all_the_osm_objects_and_copy_to_destination_lib_v2(conn, in_dc_config: dict):
    global CONF_OUTPUT_OBJ_FILES
    global CONF_OUTPUT_OBJ_RESUME_FILES_NAME

    current_folder = os.getcwd()
    output_folder = current_folder
    if in_dc_config.get(CONFIG_OUTPUT_FOLDER_FOR_THE_DSF_TEXT) is not None and in_dc_config.get(
            CONFIG_OUTPUT_FOLDER_FOR_THE_DSF_TEXT) != '':
        output_folder = in_dc_config.get(CONFIG_OUTPUT_FOLDER_FOR_THE_DSF_TEXT)

    postfix = in_dc_config.get(CONFIG_OSM_BBOX, '').replace(',', '_')
    output_dsf_text = os.path.join(output_folder, DEFAULT_DSF_TEXT_OUTPUT_FILE_NAME, '_', postfix)

    # Prepare the DSF Text file
    # 1. Read line by line from G_OUTPUT_OBJ_FILES_NAME
    # 2. Extract and rename the base_file name and add "_obj8" to it. split[0]
    # 3. Add the prefix: "OBJECT_DEF objects/{file_name}.obj" to the "dsf_text,txt" file and store its index, start in 0
    # 4. Add in a List the "OBJECT" positioning location from the extracted line (split[1])
    ##
    try:
        # Truncate output file
        with open(output_dsf_text, 'w', encoding='utf8'):
            pass

        # Copy template content into target file
        with open(DEFAULT_INPUT_DSF_TEMPLATE_FILE_NAME, 'r', encoding='utf8') as input_template:
            with open(output_dsf_text, 'w', encoding='utf8') as dsf_text_out:
                for line in input_template:
                    dsf_text_out.write(line)

        # Fetch all obj8_data rows that have seq or their 'similar_to_way_id' is NULL
        dc_dsf_objects = {}
        dc_obj8_copy_data = {}
        ls_object_position_list = []

        lib_relative_path = "objects"
        if in_dc_config.get(CONFIG_LIB_RELATIVE_PATH) is not None and in_dc_config.get(CONFIG_LIB_RELATIVE_PATH) != '':
            lib_relative_path = in_dc_config.get(CONFIG_LIB_RELATIVE_PATH)

        # Fetch optimized OBJ8_DATA rows to prepare the DSF
        stmt = 'select * from obj8_data where seq is not null'
        binds = []
        rows = exec_query_stmt(conn, stmt, binds)
        instance_files = 0
        for indx, row in list(enumerate(rows)):
            instance_files += 1
            s_path = os.path.join(lib_relative_path, row[K_FILE_NAME_OBJ8])
            dc_dsf_objects[row[K_WAY_ID]] = [indx, row[K_LAT], row[K_LON],
                                             os.path.join(lib_relative_path, row[K_FILE_NAME_OBJ8])]
            dc_obj8_copy_data[row[K_WAY_ID]] = [indx, row[K_FILE_NAME_OSM], row[K_FILE_NAME_OBJ8]]

            # Copy to library using simple stream if it was flagged in the CONFIG.json file
            if in_dc_config.get(CONFIG_ROOT_SCENERY_FOLDER_TO_COPY_OBJ8_FILES, '') != '':
                s_target_file_name = row[K_FILE_NAME_OBJ8]
                s_path = os.path.join(in_dc_config.get(CONFIG_ROOT_SCENERY_FOLDER_TO_COPY_OBJ8_FILES),
                                      lib_relative_path)
                s_source_obj8_file = os.path.join(in_dc_config.get(CONFIG_WORK_FOLDER), s_target_file_name)
                if os.path.isdir(s_path) and os.path.isfile(f'"{s_source_obj8_file}"'):
                    print(
                        f'{indx}: Destination library or source OBJ8 file are invalid.\npath: {s_path!r}\nobj8 file: {s_source_obj8_file!r}. Skipping OBJ8 copy task.')
                    continue

                # Copy file using stream
                try:
                    with open(s_source_obj8_file, 'r', encoding='utf8') as obj8_in_file:
                        s_target_file = os.path.join(s_path, s_target_file_name)
                        with open(s_target_file, 'w', encoding='utf8') as obj8_out_file:
                            print(f"Copy: {s_target_file}")
                            for read_line in obj8_in_file:
                                obj8_out_file.write(read_line)

                except FileNotFoundError as ffe:
                    print(f'{__name__}: FileNotFoundError: {s_source_obj8_file!r}\nError: {ffe}')
                    continue
                except OSError as os_err:
                    print(f'{__name__}: Failed to write from file: {s_source_obj8_file}\nError: {os_err}')
                    continue

            s_object_def = f'OBJECT_DEF {lib_relative_path}/{row[K_FILE_NAME_OBJ8]}'
            with open(output_dsf_text, 'a', encoding='utf8') as dsf_text:
                dsf_text.write(s_object_def + "\n")

        #############################
        # v1.1 implement resume rules
        # source_file = G_OUTPUT_OBJ_RESUME_FILES_NAME
        source_file = in_dc_config[CONF_OUTPUT_OBJ_RESUME_FILES_NAME]
        with open(source_file, 'r', encoding='utf8') as in_file:
            for line in in_file:
                list_data = line.split('|')  # split the pipe "|"
                if len(list_data) > 1:
                    s_source_osm_file_to_copy = list_data[0]

                # final name stored in resume file
                s_target_file_name = os.path.basename(s_source_osm_file_to_copy)

                lib_relative_path = "objects"
                if in_dc_config.get(CONFIG_LIB_RELATIVE_PATH, '') != '':
                    lib_relative_path = in_dc_config.get(CONFIG_LIB_RELATIVE_PATH)

                # Copy to library using simple stream
                if in_dc_config.get(CONFIG_ROOT_SCENERY_FOLDER_TO_COPY_OBJ8_FILES, '') != '':
                    s_path = os.path.join(in_dc_config.get(CONFIG_ROOT_SCENERY_FOLDER_TO_COPY_OBJ8_FILES),
                                          lib_relative_path)

                    s_source_obj8_file = os.path.join(in_dc_config.get(CONFIG_WORK_FOLDER), s_target_file_name)
                    if os.path.isdir(s_path) and os.path.isfile(f'"{s_source_obj8_file}"'):
                        print(
                            f'{instance_files}: Destination library or source OBJ8 file are invalid.\npath: {s_path!r}\nobj8 file: {s_source_obj8_file!r}. Skipping OBJ8 copy task.')
                        continue

                    # Copy file using stream
                    try:
                        with open(s_source_obj8_file, 'r', encoding='utf8') as obj8_in_file:
                            s_target_file = os.path.join(s_path, s_target_file_name)
                            with open(s_target_file, 'w', encoding='utf8') as obj8_out_file:
                                print(f"Copy: {s_target_file}")
                                for read_line in obj8_in_file:
                                    obj8_out_file.write(read_line)

                    except FileNotFoundError as ffe:
                        print(f'{__name__}: FileNotFoundError: {s_source_obj8_file!r}\nError: {ffe}')
                        continue
                    except Exception as e:
                        print(f'{__name__}: Failed to write from file: {s_source_obj8_file}\nError: {e}')
                        continue

                # Write to DSF2TEXT file only if we could copy the OBJ8 file
                s_object_def = f'OBJECT_DEF {lib_relative_path}/{s_target_file_name}'
                ls_object_position_list.append(f'OBJECT {instance_files} {list_data[1]}\n')

                with open(output_dsf_text, 'a', encoding='utf8') as dsf_text:
                    dsf_text.write(s_object_def + "\n")

                instance_files += 1

        # fetch all rows from obj8_data table and prepare the bottom part of the DSF text file
        ls_object_position_list.clear()
        stmt = 'select seq, way_id, lat, lon, similar_to_way_id, rotation from obj8_data'
        rows = exec_query_stmt(conn, stmt)
        for indx, row in list(enumerate(rows)):
            col_seq = row[K_SEQ]
            col_way_id = row[K_WAY_ID]
            col_similar_to_way_id = row[K_SIMILAR_TO_WAY_ID]

            if col_seq is None and col_similar_to_way_id is not None and dc_dsf_objects.get(
                    col_similar_to_way_id) is not None:
                ls_object_position_list.append(
                    f'OBJECT {dc_dsf_objects.get(col_similar_to_way_id)[0]} {row[K_LON]} {row[K_LAT]} 0.00\n')  # {row[K_ROTATION]}
            else:
                ls_object_position_list.append(
                    f'OBJECT {dc_dsf_objects.get(col_way_id)[0]} {row[K_LON]} {row[K_LAT]} 0.00\n')  # {row[K_ROTATION]}

        # Write OBJECTS into the dsf_text, always come after the OBJECT_DEF
        if len(ls_object_position_list) > 0:
            with open(output_dsf_text, 'a', encoding='utf8') as dsf_text:
                dsf_text.writelines(ls_object_position_list)

        print(
            f"\n---> Finished writing to: {output_dsf_text!r}. Instances/meshes: {instance_files}/{len(ls_object_position_list)}\n")

        # Execute DSF2Text on the copied "dsf_obj8.txt" file
        # The output_folder is where we place the "dsf2txt.txt" file to convert to DSF
        if platform.system().lower() == 'windows':
            # For Windows OS we will construct an absolute paths
            # dsf_tool_bin = '{}'.format( os.path.join(current_folder, output_folder, 'DSFTool.exe') )
            dsf_tool_bin = '{os.path.join(current_folder, output_folder, "DSFTool.exe")}'
            source_dsf_file = os.path.join(f'{current_folder}', output_dsf_text)
            os_command = 'type {} | {} -text2dsf - {}.dsf'.format(source_dsf_file, dsf_tool_bin,
                                                                  os.path.join(current_folder, output_dsf_text))

        else:
            dsf_tool_bin = os.path.join(output_folder, 'DSFTool')
            os_command = f'cat {output_dsf_text} | {dsf_tool_bin} -text2dsf - {output_dsf_text}.dsf'

        print(f"DSF2Text:\n{os_command}")

        try:
            result = subprocess.check_output(os_command, shell=True)
            print(f"\nDSFTool Result:\n{result}")

        except FileNotFoundError as file_not_found_err:
            print(file_not_found_err)
            print(f'''
[Warning] Failed to execute: DSFTool.

Check if it is located in the same folder as the {output_dsf_text!r} file.
You can manually convert the {DEFAULT_DSF_TEXT_OUTPUT_FILE_NAME!r} to DSF using the DSFTool:
Linux:
> cat {DEFAULT_DSF_TEXT_OUTPUT_FILE_NAME} | DSFTool -text2dsf - output.dsf
Windows:
> type {DEFAULT_DSF_TEXT_OUTPUT_FILE_NAME} | .\\DSFTool.exe -text2dsf - output.dsf

''')
        # .\DDSTool.exe - -png2dxt3 - -std_mips.\building_texture_1k.png.\building_texture_1k.dds
        # find ./ -type f -name "*.obj" -exec sed -i 's/.png/.dds/gI' {} \;

    except Exception as e:
        print(f"Fail to write to {output_dsf_text!r} file.\n{e}")
        sys.exit(1)

    return ""



def initialize_database (in_dc_config):
    global G_TEMP_FOLDER

    in_dc_config["db_file"] = f'{G_TEMP_FOLDER}/{G_DB_FILE}_{in_dc_config.get(CONFIG_OSM_BBOX).replace(',', '_')}.sqlite'

    db = create_db(in_dc_config)
    if not db:
        print("Failed to connect to database, aborting program.")
        sys.exit(1)

    init_tables_metatdata()  # initialize the SQLite tables as a set of commands

    drop_all_tables(db)
    create_tables(db)


    return db

# ################################
# ################################
# ####  MAIN MAIN MAIN #########
# ################################
# ################################

def main(db, in_dc_config: dict):
    global G_PREPARED_FILES_TO_PROCESS
    global G_TEMP_FOLDER
    global CONFIG_OSM_BBOX
    global CONFIG_WORK_FOLDER
    global CONFIG_DEBUG_WAY_ID
    global CONFIG_WORK_FOLDER_IS_ABSOLUTE_PATH

    os.makedirs(G_TEMP_FOLDER, exist_ok=True)

    ## Validate and initialize key CONFIGURATION parameters
    if in_dc_config.get(CONFIG_FILTER_OUT_EVERY_NTH_MESH) is not None:
        if int(in_dc_config.get(CONFIG_FILTER_OUT_EVERY_NTH_MESH)) < 3 or int(
                in_dc_config.get(CONFIG_FILTER_OUT_EVERY_NTH_MESH)) > 10:
            print(f'{CONFIG_FILTER_OUT_EVERY_NTH_MESH!r} is not in the correct bounds.Setting to 5')
            in_dc_config[CONFIG_FILTER_OUT_EVERY_NTH_MESH] = 5

    # v25.07.1 read mode
    if in_dc_config.get(CONFIG_MODE, "") == "":
        in_dc_config[CONFIG_MODE] = OPT_MODE_OBJ

    # v25.05.1
    if in_dc_config.get(CONFIG_OVERPASS_URL) is None:
        in_dc_config[CONFIG_OVERPASS_URL] = DEFAULT_OVERPASS_URL

    # Force initialization of log folder.
    if in_dc_config.get(CONFIG_LOG_FOLDER) is None:
        in_dc_config[CONFIG_LOG_FOLDER] = f'{DEFAULT_LOG_FOLDER}'

    if not os.path.isdir(in_dc_config.get(CONFIG_LOG_FOLDER)):
        try:
            os.mkdir(in_dc_config.get(CONFIG_LOG_FOLDER))
        except OSError as ose:
            print(f'Failed to create "{in_dc_config.get(CONFIG_LOG_FOLDER)!r}" folder.\n{ose}')
            sys.exit(1)

    # Set the output log files with the "log folder"
    resume_obj_file = os.path.join(in_dc_config.get(CONFIG_LOG_FOLDER), CONF_OUTPUT_OBJ_RESUME_FILES_NAME)
    generate_obj_file_log = os.path.join(in_dc_config.get(CONFIG_LOG_FOLDER), CONF_OUTPUT_OBJ_FILES)
    osm_to_obj_blend_log = os.path.join(in_dc_config.get(CONFIG_LOG_FOLDER), CONF_OUTPUT_OSM_TO_OBJ_BLEND_LOG_FILENAME)

    in_dc_config[CONF_OUTPUT_OBJ_FILES] = f'{generate_obj_file_log}_{in_dc_config.get(CONFIG_OSM_BBOX, '').replace(',', '_')}.txt'
    in_dc_config[CONF_OUTPUT_OBJ_RESUME_FILES_NAME] = f'{resume_obj_file}_{in_dc_config.get(CONFIG_OSM_BBOX, '').replace(',', '_')}.txt'
    in_dc_config[CONF_OUTPUT_OSM_TO_OBJ_BLEND_LOG_FILENAME] = f'{osm_to_obj_blend_log}_{in_dc_config.get(CONFIG_OSM_BBOX, '').replace(',', '_')}.txt'

    # v25.08.1
    dir_path = os.path.dirname(os.path.realpath(__file__))
    dc_config[CONFIG_WORK_FOLDER_IS_ABSOLUTE_PATH] = False  # initialized
    work_path = dc_config.get(CONFIG_SCRIPT_WORK_FOLDER, os.path.join(dir_path, "out") )
    out_path = work_path
    if Path(work_path).is_absolute():
        out_path = work_path
        dc_config[CONFIG_WORK_FOLDER_IS_ABSOLUTE_PATH] = True

    # v25.08.1 Store the work path folder for later use
    dc_config[CONFIG_WORK_FOLDER] = out_path

    # Step 1 - Fetch data. Decide if to use DEBUG and ad-hoc "way_id" list, or to use overpass/pre-defined osm file
    bbox_coordinates = in_dc_config.get(CONFIG_OSM_BBOX, '')
    overpass_json_file_name = in_dc_config.get(CONFIG_OSM_JSON_FILE, '')

    # The "main_osm_id_list": will hold the list of "<way>" nodes and their "id" (way_id), rest of data resides in the sqlite.
    way_counter = 0

    # we don't want to drop all data if we want to use: "CONFIG_DEBUG_WAY_ID"
    # in_building_id_list = [690633916] #[572034671] ##[572034673]  # Debug

    debug_way_id = in_dc_config.get(CONFIG_DEBUG_WAY_ID)
    # if debug_way_id is None:
    #     drop_all_tables(db)
    #     create_tables(db)
    if debug_way_id is not None:
        main_osm_id_list = debug_way_id
    else:
        # the "db" is still not initialized. We will call initialize_database()
        main_osm_id_list = fetch_osm_data_in_bbox_and_call_task_by_mode_value(db=db, bbox_coord=bbox_coordinates,
                                                                              in_dc_config=in_dc_config,
                                                                              in_overpass_json_file_name=overpass_json_file_name)


if __name__ == "__main__":
    print(f'{os.path.basename(__file__)} - v{G_MAJOR_VER}.{G_MINOR_VER}.{G_FIX_VER}\nWritten by Sa\'ar\n')
    start_time = time.time()
    # https://www.geeksforgeeks.org/command-line-arguments-in-python/
    # total arguments
    dc_config = read_config_file()
    DB = None

    try:
        main(DB, dc_config)

    except Error as main_error:
        print(main_error)

    except Exception as any_error:
        print(any_error)

    finally:
        if DB is not None:
            DB.close()
            print("Disconnected from database")

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f">> Execution time: {elapsed_time:.6f} seconds <<")

    sys.exit(0)

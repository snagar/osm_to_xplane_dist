"""Blender script to prepare and shape the mesh.
Called from osm_to_obj8.py script"""
# import sys
import logging
import datetime
import ast
from logging import raiseExceptions
from pathlib import Path
import os
import importlib.util
# import math
import copy
import sys
import xml
import xml.etree.ElementTree as ET
import random
import sqlite3
from sqlite3 import Error
import bpy
import bmesh
import mathutils
from mathutils import Vector

# /mnt/virtual/tools/blender-3.6.10-linux-x64/blender ~/programming/git/osm_to_obj/blender/empty.blend --background --python /home/xplane/programming/git/osm_to_obj/blender-addon/run_ImportAndFlipNormals.py -- "/home/xplane/programming/git/osm_to_obj/out/xx_690633916_cube.obj"


# https://www.delftstack.com/howto/python/python-run-another-python-script/
# https://blender.stackexchange.com/questions/299745/how-to-open-an-image-in-uv-editor-via-script

# https://blender.stackexchange.com/questions/6173/where-does-console-output-go
# https://blender.stackexchange.com/questions/144589/how-to-make-object-translations-in-the-uv-editor-scripting-blender-python-api#144829
# https://docs.blender.org/api/current/bmesh.html
# https://blender.stackexchange.com/questions/174551/how-to-select-vertices-then-convert-to-face-selection-with-python
# https://docs.blender.org/api/current/bmesh.types.html
# https://blender.stackexchange.com/questions/711/how-to-add-a-uv-map-to-a-mesh-using-python
# https://www.geeksforgeeks.org/random-numbers-in-python/

CONFIG_USE_SQLITE_FLOW = "use_sqlite_flow"  # boolean if to use the code logic that stores and filter most data from the sqlte DB
G_OBJ8_DATA_TABLE = 'obj8_data'
K_FILE_NAME_OBJ8 = 'file_name_obj8'
K_WAY_ID = 'way_id'
CONFIG_BLENDER_VERSION = 'blender_version'  # number


class FaceInfo:
    """Class that stores the face information for easier manipulation"""
    # def __init__(self, in_index: int, in_b_is_square: bool, in_max_edge_len: float):
    #     self.index = in_index
    #     self.bIsSquare = in_b_is_square
    #     self.maxEdgeLength = in_max_edge_len

    def __init__(self, other):
        self.index = other.index
        self.b_is_square = other.bIsSquare
        self.max_edge_length = other.maxEdgeLength

    def __str__(self):
        """ Used like tostring when printing the class."""

        return f'FaceInfo(Index: {self.index}, bIsSquare: {self.b_is_square}, maxEdgeLength:{self.max_edge_length}, face: {self.face}'

    def tostring(self):
        """ To String """
        return f'FaceInfo(Index: {self.index}, bIsSquare: {self.b_is_square}, maxEdgeLength:{self.max_edge_length}'

    def find_if_square_and_max_edge_length(self):  # <indx, bool> Face index + True/False is square
        """Find if our mesh is a square in shape or not. """
        longest_edge_in_mesh = 0.0

        ls_distances = []
        max_face_edge_length = -1
        for edge in self.face.edges:
            f_distance = distance_vec(edge.verts[0].co, edge.verts[1].co, True)
            max_face_edge_length = max(f_distance, max_face_edge_length)

            # print (f"\tDistance: {f_distance}") # Debug
            ls_distances.append(distance_vec(edge.verts[0].co, edge.verts[1].co, True))

        longest_edge_in_mesh = max(max_face_edge_length, longest_edge_in_mesh)

        # square = first value IN LIST should be THE same as all others.
        self.b_is_square = all(x == ls_distances[0] for x in ls_distances)
        self.max_edge_length = longest_edge_in_mesh

    index = 0
    b_is_square = False
    max_edge_length = 0

    face = bmesh.types.BMFace

    co_list = []
    uv_verts = []  # holds uv vertices coordinates


# END CLASS
# END CLASS
# END CLASS
# END CLASS

def print(in_message=""):
    """This function will override the original 'print'
    function and will log the text to an external file."""

    logger.info(f'{datetime.datetime.now()} %s', in_message)


def eval_from_text(in_text):
    """ eval_from_text() function, returns None if ast.literal_eval() fails """
    try:
        return ast.literal_eval(in_text)
    except Exception as ve:
        print(f'Error:\n{ve}\nFor: {in_text}')
        return None


def expand_ranges(input_list):
    expanded_list = []

    for item in input_list:
        if '--' in item:  # Check if it's a range
            start, end = item.split('--')
            start, end = int(start), int(end)
            expanded_list.extend(str(i) for i in range(start, end + 1))
        else:
            expanded_list.append(item)

    return expanded_list


def xml_search_tag_with_attrib_value(in_parent=xml.etree.ElementTree.Element, tag="", attrib="", value="") -> xml.etree.ElementTree.Element:
    """Search for an XML node based on tag name, its attribute and value"""
    # Texture Mappings from XML file
    for child in in_parent:
        if child.tag == tag and child.get(attrib) == value:
            return child


def xml_read_attrib(in_node: xml.etree.ElementTree.Element, attrib="", in_default=""):
    """Get the value of an attribute, return default if attribute was not found."""
    return in_node.get(key=attrib, default=in_default)


def xml_read_text_and_weights_as_list(in_parent: xml.etree.ElementTree.Element, tag: str = "") -> []:
    """Read the text and the weight attribute from all tags with same name"""
    ls_zones = []
    ls_weights = []
    for child in in_parent.iter(tag):
        ls_text = child.text.split(',')

        if len(ls_text) < 4:
            print(f'Error reading {tag}, does not have at least four values: {ls_text!r}. Skipping tag.')
            continue

        s_default_weight = "1"
        ls_zones.append(ls_text)
        s_weight = child.get("weight", s_default_weight)

        if s_weight.isnumeric():
            ls_weights.append(int(s_weight))
        else:
            ls_weights.append(int(s_default_weight))

    return ls_zones, ls_weights


def find_node_bucket_based_on_metadata_or_dimension(in_dc_config: dict, in_dc_indx_by_metadata: dict = None, in_dc_indx_by_length: dict = None, in_vertex_max_length: float = 0.0):
    """ The function find_node_bucket_based_on_metadata_or_dimension() will evaluate the:
    "metadata information" first, to see if we can pick an index from it.
    If it fails, then it will fall back to: "index based max_length" logic.
    """

    """ 
        1. Loop over all "way_meta" keys (received from "dc_config{}")
        1.1 sub loop over all 'in_dc_indx_by_metadata' key/values.                
        Pick the index based on the highest ranking, while the first key equals to "5" points and any sub key to "1".
    """
    # v1.2 Added support of level key list
    # list_of_level_keys = in_dc_config.get('level_keys_list', [])
    # if not isinstance(list_of_level_keys, list):
    #     list_of_level_keys = []

    picked_index = ""
    highest_grade = 0

    # v1.2 Expand custom ranges "--"
    for k_dc_indx, v_dc_grade in in_dc_indx_by_metadata.items():
        for k, v in v_dc_grade.items():
            in_dc_indx_by_metadata[k_dc_indx][k] = expand_ranges(v)

    print(f'{in_dc_config.get("way_meta")=}')  # debug

    if in_dc_indx_by_metadata is not None:
        highest_grade = 0
        for k_dc_indx, v_dc_grade in in_dc_indx_by_metadata.items():  # loop over uv_config.index_meta grading dict
            # Validate we have dictionary type
            if not isinstance(v_dc_grade, dict):
                continue

            cumulative_grade = 0
            # loop over the way_id metadata we received.
            for enum_meta, (km, vm) in enumerate(in_dc_config.get("way_meta", {}).items()):
                grade = 0
                # Check if the way_key is present in the v_dc_grade[1] dictionary.
                if v_dc_grade.get(km, None) is not None:
                    tab = '\t' if enum_meta > 0 else ''
                    print(f'{tab}way_key: "{km}" found for index_meta: "{k_dc_indx}"')  # debug

                    # check if the "key_value" is in the "values list"
                    if vm in v_dc_grade.get(km):  # returns the list
                        # check if it is the first one:
                        if km == list(v_dc_grade.keys())[0]:
                            grade = 5
                        else:
                            grade = 1

                        cumulative_grade += grade

                        # debug
                        print(
                            f'\tway_key: "{km}" received grade:"{grade}". cumulative_grade: {cumulative_grade!r}')  # Found: "{vm}" in: ({km}:{v_dc_grade.get(km)})')

            # v1.2 moved the grading test after finishing the attribute evaluation loop.
            if cumulative_grade > highest_grade:
                highest_grade = cumulative_grade
                picked_index = k_dc_indx

    if picked_index is not None and picked_index != "":
        print(
            f'\nFound index based on metadata information. Index {picked_index!r} with grade of: {highest_grade!r}')
        return picked_index, ""

    # Read uv_xml_config.xml index tag and find the correct bucket our mesh belongs to based on its max wal length.
    if in_dc_indx_by_length is None:
        in_dc_indx_by_length = {}

    print ("Did not found texture tile based on osm metadata, fallback to 'wall based length' indexing.")  # v1.2 info
    picked_index = "1"  # initialize with the first "set"
    for indx, bucket in in_dc_indx_by_length.items():
        if in_vertex_max_length <= bucket:
            return indx, ""

        picked_index = indx

    return picked_index, "Could not find matching bucket, returned the last one."


# # END utility functions ####
# # END utility functions ####
# # END utility functions ####

########################
# Manipulate UV MAP
########################
def uv_mapping_based_xml(conn, in_obj, in_dc_config, in_mesh_dimension):
    """Read XML Config File "blend_uv_xml_config_file" """
    try:
        me = bpy.context.edit_object.data
        bm = bmesh.from_edit_mesh(me)

        tree = ET.parse(in_dc_config["blend_uv_xml_config_file"])
        root = tree.getroot()
        n_index = root.find('index')
        n_index_meta = root.find('index_meta')  # v1.1
        n_uv_fix = root.find('uv_rotation_fix')
        if n_index is None:
            print("No <index> element was found. Aborting !!")
            sys.exit(1)

        dc_uv_fix = {}
        dc_index_node = eval_from_text(n_index.text.strip())
        dc_index_meta_node = eval_from_text(n_index_meta.text.strip())  # v1.1 The strip() function is important to remove malformed spaces and chars that will fail the evaluation

        if n_uv_fix is None:
            dc_uv_fix = {}
        else:
            dc_uv_fix = eval_from_text(n_uv_fix.text.strip())

        # Force dictionary types
        if not isinstance(dc_uv_fix, dict):
            dc_uv_fix = {}
        if not isinstance(dc_index_node, dict):
            dc_index_node = {}
        if not isinstance(dc_index_meta_node, dict):
            dc_index_meta_node = {}

        # Gather Mesh faces information
        last_index_before_roof_creation, top_bottom_faces_list, dc_face_info = gather_faces_info_and_top_bottom(bm)
        # longest_edge_in_mesh = find_longest_edge(bm)

        # Calculate top most face area
        # https://blender.stackexchange.com/questions/13974/how-to-calculate-or-get-surface-area-of-a-mesh
        top_face_info = dc_face_info[top_bottom_faces_list[0]]
        mesh_faces_no = len(bm.faces)
        top_face_area = top_face_info.face.calc_area()

        # we gather the object dimensions at
        print(f'mesh_dimension: {in_mesh_dimension}')
        mesh_max_length = in_mesh_dimension.y if in_mesh_dimension.y > in_mesh_dimension.x else in_mesh_dimension.x

        print(
            f"top_bottom_faces_list: {top_bottom_faces_list}, mesh_faces_no: {mesh_faces_no}, top_face_area: {top_face_area}")
        print(f"mesh_max_length: {mesh_max_length}, last_index_before_roof_creation: {last_index_before_roof_creation}")

        # Get the XML Set based on max edge length
        texture_index, msg = find_node_bucket_based_on_metadata_or_dimension(in_dc_config, dc_index_meta_node, dc_index_node, mesh_max_length)
        if msg != '':
            print(msg)
        else:
            print(f"Got {texture_index=}")

        # Get the set and randomly pick one type from each texture for roof and walls
        n_set = xml_search_tag_with_attrib_value(root, "set", "index", str(texture_index))
        print(f"n_set: {n_set}")

        ls_roofs, ls_weights = xml_read_text_and_weights_as_list(n_set, 'roof')
        rnd_roof = random.choices(ls_roofs, ls_weights)[0]
        # print (f'Roof:\n{ls_roofs}\n{ls_weights}')

        ls_weights.clear()
        ls_wall, ls_weights = xml_read_text_and_weights_as_list(n_set, 'wall')
        rnd_wall = random.choices(ls_wall, ls_weights)[0]
        # print (f'Wall:\n{ls_wall}\n{ls_weights}')

        ls_wall_door, ls_weights = xml_read_text_and_weights_as_list(n_set, 'wall_w_door')
        rns_wall_door = random.choices(ls_wall_door, ls_weights)[0]
        # print (f'WallDoor:\n{ls_wall_door}\n{ls_weights}')

        ls_wall_win, ls_weights = xml_read_text_and_weights_as_list(n_set, 'wall_w_win')
        rnd_wall_win = random.choices(ls_wall_win, ls_weights)[0]
        # print (f'WallWin:\n{ls_wall_win}\n{ls_weights}')

        print(f'Random rnd_roof: {rnd_roof}')
        print(f'Random rnd_wall: {rnd_wall}')
        print(f'Random rns_wall_door: {rns_wall_door}')
        print(f'Random rnd_wall_win: {rnd_wall_win}')

        # return None  # debug

        uv_layer = bm.loops.layers.uv.verify()
        bmesh.update_edit_mesh(me)

        # Add Roof to top face if it has "only" 4 edges. It will Extrude the top face.
        for face in bm.faces:
            if face.index == top_bottom_faces_list[0]:
                # calculate edges lengths
                no_of_edges = len(face.edges)
                edges_len = str()
                real_edges_len = str()
                for indx, ed in enumerate(face.edges):
                    if indx > 0:
                        edges_len += ','
                        real_edges_len += ','

                    edges_len += str(round(ed.calc_length()))
                    real_edges_len += str(round(ed.calc_length(), 3))

                if in_dc_config.get(CONFIG_USE_SQLITE_FLOW, False):
                    in_binds = [no_of_edges, edges_len, real_edges_len, in_dc_config.get(K_WAY_ID)]
                    in_stmt = f'update {G_OBJ8_DATA_TABLE} set edges=?, edges_length=?, edges_length_real=? where way_id=?'
                    conn.execute("BEGIN TRANSACTION;")
                    exec_stmt(conn, in_stmt, in_binds)
                    conn.execute("END TRANSACTION;")

                print(f'{edges_len=}, {real_edges_len=}')  # debug

                if len(face.edges) == 4:
                    # logger.info(f'{datetime.datetime.now()} face: {face}, type: {type(face)}, face.edges: {face.edges}, len: {len(face.edges)}')
                    logger.info('%s Trying roof for 4 edges face. ', datetime.datetime.now())
                    # Extrude
                    ret = bmesh.ops.extrude_face_region(bm, geom=[face])

                    verts = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
                    faces = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMFace)]
                    bmesh.ops.translate(bm, vec=face.normal * -1.7, verts=verts)

                    # logger.info(f'{datetime.datetime.now()}\t  verts: {verts}, len: {len(faces[0].edges)} ')

                    # Collapse the short edges to create a roof like look
                    e1, e2, e3, e4 = faces[0].edges
                    if (e1.calc_length() + e3.calc_length()) < (e2.calc_length() + e4.calc_length()):
                        edges = [e1, e3]
                    else:
                        edges = [e2, e4]
                    bmesh.ops.collapse(bm, edges=edges)
                    bmesh.update_edit_mesh(me)
                else:
                    logger.info('%s\t Face does not have 4 edges: %s, skipping ', datetime.datetime.now(), len(face.edges))
                    break

        dc_face_info.clear()  # Clear before refresh
        dummy_last_index_before_roof_creation, dummy_top_bottom_faces_list, dc_face_info = gather_faces_info_and_top_bottom(bm)
        # we Won't use dummy_last_index_before_roof_creation

        print('\tafter roof.')
        print("\n\n")

        # Print face info for debug
        print(f"dc_face_info count: {len(dc_face_info)}")

        # debug
        # for key, val in dc_face_info.items():
        #     print (f'key: {key}, value: {val}')

        uv_faces = {}  # <face index, dict <uv indx, co> >
        b_used_uv_door = False
        for face in bm.faces:

            # print(f"Face #{face.index}\t\t{type(face)}")
            uv_faces[face] = []  # initial as a list
            for corner in face.loops:  # corner is BMLoop
                uv_vert = corner[uv_layer]  # uv_layer = BMLayerItem type
                # print (f'\tvert.co:{corner.vert.co} uv_layer: {uv_layer} uv_vert: {uv_vert}') # vert is BMVert, the vertice holds the 3D View port coordinates.
                uv_faces[face].append(uv_vert)

        # Loop over all faces and gather uv random settings based on max edge length
        i_wall_counter = 0
        i_window_counter = 0
        top_face_index = top_bottom_faces_list[0]

        for face, uv_list_verts in uv_faces.items():
            # print ('====>\n')
            # print (f'\tEvaluating Face Index: {face.index}. Is Top/Bottom: {face.index in top_bottom_faces_list}')

            if dc_face_info.get(face.index) is not None:
                face_info = dc_face_info[face.index]  # get the CLASS for the face index
            else:
                print(f'Face Index: {face.index} is not present in dc_face_info. dc_face_info length: {len(dc_face_info)}. Skipping...')
                continue

            # Pick uv texture zone
            s_zone_type = ""
            rnd_zone = []
            if face.index in top_bottom_faces_list or face.index > last_index_before_roof_creation:
                rnd_zone = copy.deepcopy(rnd_roof)
                s_zone_type = "roof"
                print(f'\tRoof face: {face.index}, face_info: {face_info}')

                # Handle top faces that have more than 4 edges
                if face.index == top_face_index:  # top_bottom_faces_list[0]
                    top_face_info = dc_face_info[face.index]
                    top_face_info.face = face

                    top_face = face
                    if len(top_face.edges) > 4:
                        print('>>> Analyzing top face with more than 4 edges <<<')
                        mesh = in_obj.data
                        uv_layer = bm.loops.layers.uv.verify()
                        top_face_info.uv_verts.clear()

                        for corner in top_face.loops:  # corner is BMLoop
                            uv_vert = corner[uv_layer]  # uv_layer = BMLayerItem type
                            top_face_info.uv_verts.append(corner[uv_layer])
                            # print (f'\t Corner.co:{corner.vert.co} uv.co: {corner[uv_layer].uv} uv type: {uv_vert}') # vert is BMVert, the vertices holds the 3D View port coordinates.

                        print(f'uv_layer: {uv_layer}, len(mesh.polygons): {len(mesh.polygons)}')
                        if uv_layer is not None:  # uv_layer:
                            bpy.ops.object.mode_set(mode='EDIT')
                            bpy.ops.mesh.select_all(action='DESELECT')
                            mesh.polygons[top_face.index].select = True
                            bpy.ops.uv.select_all(action='DESELECT')
                            #                bpy.ops.uv.select(extend=False, location=(0, 0))
                            top_face.select = True
                            bpy.ops.uv.cube_project()  # bpy.ops.uv.cube_project(cube_size=550) # the higher the number the smaller the uv on the map
                            # Resize

                            uv_scale = float(rnd_zone[3])  # 0.125
                            # Position projection in the roofs x/y position
                            uv_new_x_position_vector = mathutils.Vector((float(rnd_zone[0]), float(rnd_zone[1])))
                            for uv_info in top_face_info.uv_verts:
                                uv_info.uv *= uv_scale
                                uv_info.uv += uv_new_x_position_vector

                            # The following EXTRUDE code can screw some meshes, so it is on hold for now
                            # Maybe we can try "in_set" + grab on "z" axes, to create a fake roof instead
                            # z_length=2.5
                            # # extrude top face
                            # #https://blender.stackexchange.com/questions/40247/extrude-a-mesh-by-region-using-python-script
                            # for face in bm.faces:
                            #     if face.index == top_bottom_faces_list[0]:
                            #         bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value":(0, 0, z_length)})
                            #         print ('After Extruding roof')
                            #         bpy.ops.mesh.bevel(offset_type='OFFSET', offset=z_length-1.0, affect='EDGES', offset_pct=0)
                            #         bmesh.update_edit_mesh(me)
                            #         print ('After Beveling roof')

                            # # Create a fake roof using bevel

                            if in_dc_config.get("add_bevel", False):
                                top_face.select = True
                                bpy.ops.mesh.bevel(offset_type='OFFSET', offset=0.4, affect='EDGES', offset_pct=0,
                                                   segments=3,
                                                   miter_outer='PATCH')  # miter_outer='ARC', miter_inner='ARC'
                                bmesh.update_edit_mesh(me)
                                print('After Beveling roof')

                            continue  # Do not continue with unwrapping the face for top face with more than 4 edges

                        # No uv_layer found
                        print("No uv_layer found for Top Face ???")

            else:

                if b_used_uv_door is False and face_info.max_edge_length <= 12.0:
                    rnd_zone = copy.deepcopy(rns_wall_door)
                    b_used_uv_door = True
                    s_zone_type = "wall_w_door"
                    print("\t Added Door")
                elif i_window_counter < 1 and face_info.max_edge_length <= 12.0:
                    rnd_zone = copy.deepcopy(rnd_wall_win)
                    i_window_counter += 1
                    s_zone_type = "wall_w_win"
                    print("\t Added Window")
                else:
                    rnd_zone = copy.deepcopy(rnd_wall)
                    i_wall_counter += 1
                    s_zone_type = "wall"

            # print (f'\tPicked zone: {s_zone_type}, rnd_zone: {rnd_zone!r}') ## debug
            tmp_zone = []
            for s in rnd_zone:
                tmp_zone.append(float(s))
            rnd_zone.clear()
            rnd_zone = copy.deepcopy(tmp_zone)

            # Wrap the MESH on the uv map CCW
            triangle = 3
            uv_count = len(uv_list_verts)
            half_uv_count = uv_count * 0.5

            if uv_count < 3:
                print(f'>>> ERROR in face index: {face.index}, uv count is less than 3. Skipping... <<<')
                continue

            print(f'\trnd_zone: {rnd_zone}')
            total_x_vertex_len_ratio = rnd_zone[2]  # X vector final length
            # if our vertex number > 3 we calculate half of the count since we have 2 parallel vectors, one for base and one for wall height.
            # if our vertex number < 4 we divide by 4, so the base of the uv triangle won't be longer than the texture zone itself.
            f_part = total_x_vertex_len_ratio / (half_uv_count if uv_count > triangle else 4)
            x = rnd_zone[0]  # x start pos
            y = rnd_zone[1]  # y start pos
            # Debug Info
            # print (f'\tPicked zone: {s_zone_type}, half_uv_count: {half_uv_count}, Start position: {x},{y}, end position: {rnd_zone[2]}, {rnd_zone[3]}. Total_x_length: {total_x_vertex_len_ratio}, Height_ratio: {rnd_zone[3]}')
            print(f'\tUV face {face.index} has: {uv_count} edges. {f_part=}')

            indx = int(0)
            uv_list_verts[indx].uv = Vector((x, y))
            step = total_x_vertex_len_ratio / (1 if half_uv_count - 1 <= 0 else half_uv_count - 1)
            if uv_count == triangle:
                # right
                x = rnd_zone[0] + rnd_zone[2]
                uv_list_verts[1].uv = Vector((x, y))
                # center top
                x = (rnd_zone[0] + rnd_zone[2]) - (rnd_zone[2] * 0.5)  # triangle
                y = rnd_zone[1] + rnd_zone[3]
                uv_list_verts[2].uv = Vector((x, y))

            else:
                for i in range(1, int(half_uv_count)):
                    indx += 1
                    x += step
                    uv_list_verts[indx].uv = Vector((x, y))

                # top face edge
                indx += 1
                y = rnd_zone[1] + rnd_zone[3]
                uv_list_verts[indx].uv = Vector((x, y))

                for i in range(1, int(half_uv_count)):  # elevation
                    indx += 1
                    x -= step
                    uv_list_verts[indx].uv = Vector((x, y))

            # debug
            # for indx, vec in enumerate(uv_list_verts):
            #     print (f'\t{indx}: { vec.uv }') # debug

            # try to rotate uv based on the XML heuristics.
            # TODO: we need to find a better way to find the face UV rotation and then rotate it correctly
            # https://docs.blender.org/api/current/bpy.ops.mesh.html#bpy.ops.mesh.uvs_rotate
            face.select = True
            # print (f'\t{last_index_before_roof_creation = }')
            if face.index < last_index_before_roof_creation:
                if face.index not in top_bottom_faces_list and dc_uv_fix.get('wall', '') != '':  # Wall face
                    b_use_ccw = bool(dc_uv_fix.get('wall') == "ccw")
                    # print (f'Rotating Wall uv face ccw={b_use_ccw}, index: {face.index}');
                    bpy.ops.mesh.uvs_rotate(use_ccw=b_use_ccw)
                elif face.index == top_bottom_faces_list[0] and dc_uv_fix.get('top', '') != '':  # Top Face
                    b_use_ccw = bool(dc_uv_fix.get('top') == "ccw")
                    # print (f'Rotating Top uv face ccw={b_use_ccw}, index: {face.index}');
                    bpy.ops.mesh.uvs_rotate(use_ccw=b_use_ccw)

                else:
                    print(f'NOT Rotating uv of face index: {face.index}')
            else:
                print(f'NOT Rotating roofs uv of face index: {face.index}')
            face.select = False

    except FileNotFoundError as fife:
        print(f'\n{fife}\n')
        sys.exit(1)


def gather_faces_info_and_top_bottom(bm):
    """Gather faces info into dictionary of FaceInfo class """

    # me = bpy.context.edit_object.data
    # bm = bmesh.from_edit_mesh(me)

    # For simple cubic shapes
    highest_face_index_before_roof = 0
    dc_faces_co = {}  # key=index, value = list []
    dc_face_info = {}

    for face in bm.faces:
        index = face.index
        highest_face_index_before_roof = max(face.index, highest_face_index_before_roof)
        # if face.index > highest_face_index_before_roof:
        #     highest_face_index_before_roof = face.index

        # init class
        face_info = FaceInfo
        face_info.index = face.index
        face_info.face = face
        face_info.find_if_square_and_max_edge_length(self=face_info)

        co_list = []
        for corner in face.loops:  # gather face coordinates
            co_list.append(corner.vert.co)

        dc_faces_co[index] = co_list
        face_info.co_list = co_list.copy()
        # dc_face_info[index] = copy.deepcopy(face_info)
        dc_face_info[index] = face_info

    lowest_z_indx = 0
    highest_z_indx = 0
    lowest_z_sum = 0.0
    highest_z_sum = 0.0
    for enum, (indx, list_co) in enumerate(dc_faces_co.items()):
        sum_z = 0.0
        for vec in list_co:  # loop over coordinate Vector<x,y,z> and add "z"
            sum_z += vec.z

        # print ("indx: %d, sum_x: %.3f, (%.3f, %.3f, %.3f) " % ( indx, sum_z, vec.x, vec.y, vec.z ) )
        # Check lowest sum z
        if sum_z < lowest_z_sum or enum == 0:
            lowest_z_sum = sum_z
            lowest_z_indx = indx
        # Check highest sum z
        if sum_z > highest_z_sum or enum == 0:
            highest_z_sum = sum_z
            highest_z_indx = indx

    print(
        f'\n\nThe bottom face idx: {lowest_z_indx} ({lowest_z_sum})\nThe top face idx: {highest_z_indx} ({highest_z_sum})\n')
    return highest_face_index_before_roof, [highest_z_indx, lowest_z_indx], dc_face_info


def distance_vec(point1: Vector, point2: Vector, in_b_round=False) -> float:
    """Calculate distance between two points."""

    # https://sinestesia.co/blog/tutorials/calculating-distances-in-blender-with-python/
    # math.dist(point1, point2) python 3.8+
    if in_b_round:
        return round((point2 - point1).length)
    return (point2 - point1).length


########################
# Manipulate OVERPASS OBJ file
########################


def import_wavefront(file_path):
    """Import the "{}_osm.obj" base file as a wave form mesh file to manipulate later """
    blender_version = bpy.app.version_string
    if blender_version.startswith("4"):
        bpy.ops.wm.obj_import(filepath=file_path)
    else:
        bpy.ops.import_scene.obj(filepath=file_path)


def flip_normals():
    """Flip All Objects Normals Outside """  # Use this as a tooltip for menu items and buttons.

    for local_obj in bpy.context.scene.objects:
        if local_obj.type == 'MESH':  #'MESH':
            print(f'Flipping MESH Object: {local_obj.name}')

            bpy.context.view_layer.update()
            # bpy.ops.object.mode_set(mode='OBJECT') # This line fail the script. But I have no idea why 'EDIT' works.
            bpy.ops.object.select_all(action='DESELECT')
            local_obj.select_set(True)
            # Set Active object in layer focus to the obj
            bpy.context.view_layer.objects.active = local_obj
            # Enter EDIT mode
            bpy.ops.object.mode_set(mode='EDIT')
            # select all faces
            bpy.ops.mesh.select_all(action='SELECT')
            # Recalculate all normals to be outside
            bpy.ops.mesh.normals_make_consistent(inside=False)

            bpy.ops.object.editmode_toggle()
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            print(f"Finish Flipping MESH: {local_obj.name}")


def export_as_obj(file_path):
    """Export the mesh as WaveFront obj file."""

    print('Start Exporting all MESH Objects.')

    # seq=1
    for local_obj in bpy.context.scene.objects:
        if local_obj.type == 'MESH':  #'MESH':
            out_file_name = f"{file_path}.vn.obj"
            print(f'Trying to Export Object: {local_obj.name}')

            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.select_all(action='DESELECT')
            local_obj.select_set(True)
            bpy.context.view_layer.objects.active = local_obj
            bpy.context.view_layer.update()
            bpy.ops.wm.obj_export(
                filepath=out_file_name,
                export_selected_objects=True,  # Export selected objects only
                export_normals=True,  # Include normals
                export_materials=False,  # Exclude materials
                check_existing=False,  # Check if override file
            )

    print('Finish Exporting all MESH Objects.')


def set_material_to_object(in_dc_config):
    """Set the mesh material. Will use the texture information from config.json file"""

    # Loop over all mesh objects
    for local_obj in bpy.data.objects:
        # logger.info(f'{datetime.datetime.now()} 1. obj: {obj}')
        if local_obj.type == "MESH":
            # logger.info(f'{datetime.datetime.now()} 2. Found MESH')

            # Create a new material
            material_name = "texture"
            material = bpy.data.materials.new(name=material_name)

            # Assign the material to the object
            if local_obj.data.materials:
                local_obj.data.materials[0] = material
            else:
                local_obj.data.materials.append(material)

            # Set the base color as "Image Texture"
            # logger.info(f'{datetime.datetime.now()} 3.0 Set Base Color')
            material.use_nodes = True
            nodes = material.node_tree.nodes
            node = nodes.get("Principled BSDF")
            if node:
                print(f'4.0 Setting Node, current folder is: {os.getcwd()}')  # debug
                # Debug - use only when there is an error related to node.inputs[]
                # for nodeObj in node.inputs:  # Debug - important to understand the differences between blender versions.
                #     print(f'Obj: {nodeObj}')
                # print('4.01 After Loop Inputs')
                # End debug nodes

                node.inputs["Base Color"].default_value = (1, 1, 1, 1)  # White color

                # Specular: bpy.data.materials["texture"].node_tree.nodes["Principled BSDF"].inputs[7].default_value = 0.07
                if in_dc_config.get(CONFIG_BLENDER_VERSION, 3) == 3:
                    node.inputs["Specular"].default_value = 0.07  # v3.x: "Specular", v4.x: "Specular IOR Level"
                else:
                    node.inputs["Specular IOR Level"].default_value = 0.07  # v3.x: "Specular", v4.x: "Specular IOR Level"

                # print('4.01 After Specular settings.')  # debug

                # print('4.01 Setting x-plane GLOBAL_specular') ## GLOBAL_specular replaces ATTR_shiny_rat
                bpy.ops.object.add_xplane_material_attribute()
                # logger.info(f'{datetime.datetime.now()} 4.02 material: {material}')

                # bpy.data.materials["texture"].xplane.customAttributes[0]
                material.xplane.customAttributes[0].name = "GLOBAL_specular"
                material.xplane.customAttributes[0].value = "0.07"

                logger.info(f'{datetime.datetime.now()} 4.03 custom attrib name: {material.xplane.customAttributes[0].name!r}')

                ###########################
                # Add an Image Texture node
                image_texture_node = nodes.new(type="ShaderNodeTexImage")
                image_texture_node.location = (node.location.x, node.location.y)

                # determine path based on config.json
                image_name = os.path.basename(in_dc_config["blend_base_texture_name"])
                image_base_folder = os.path.dirname(in_dc_config["blend_base_texture_name"])

                if Path(in_dc_config["blend_base_texture_name"]).is_absolute():
                    image_filepath = in_dc_config["blend_base_texture_name"]
                else:
                    image_filepath = os.path.join(in_dc_config.get("work_folder", os.getcwd()), image_base_folder,
                                                  image_name)

                if in_dc_config.get("blend_load_texture") is True:
                    image_texture_node.image = bpy.data.images.load(filepath=image_filepath)  # Load the texture
                    print(f"4.1 Loaded Texture: {image_filepath}.")

                    image = bpy.data.images.get(image_name)
                    if not image:
                        logger.info(f'{datetime.datetime.now()} 4.2 Trying to re-load uv_image: %s.', image_name)
                        bpy.ops.image.open(filepath=image_filepath)
                        image = bpy.data.images.get(image_name)

                    logger.info(f'{datetime.datetime.now()} 4.3 Image info: %s.', image)
                    logger.info(f'{datetime.datetime.now()} 4.4 Workspace: %s.',
                                bpy.context.window_manager.windows[0].workspace)

                else:
                    logger.info(f'{datetime.datetime.now()} 4.1 Setting Texture: %s, not loading.', image_name)
                    image_texture_node.image = bpy.data.images.new(name=image_name, width=1024,
                                                                   height=1024)  # Set the texture name without loading

                # # Set uv image area
                # for area in bpy.context.screen.areas:
                #     logger.info(f'{datetime.datetime.now()} Area Type: { area.type }\t{area}.')
                #     if area.type in ['IMAGE_EDITOR', 'VIEW_3D']:
                #         area.type = 'IMAGE_EDITOR'
                #         area.ui_type = 'UV'  # bpy.context.area.ui_type = 'UV'   # https://blender.stackexchange.com/questions/159358/setting-the-context-window-screen-layout-explicitly-in-bpy
                #         area.spaces.active.image = image
                #         logger.info(f'{datetime.datetime.now()} {area.type}: Setting area.spaces.active.image to: {area.spaces.active.image}.')
                #         area.type = 'VIEW_3D'
                #         logger.info(f'{datetime.datetime.now()} Set area type back to: {area.type}.')

                # Connect the nodes
                material.node_tree.links.new(image_texture_node.outputs["Color"], node.inputs["Base Color"])

                print(f"Material {material_name!r} created for object {local_obj.name!r}.")
            else:
                print(f"Error: Principled BSDF node not found in material nodes for object {local_obj.name!r}.")
        else:
            print(f"kipping non-mesh object {local_obj.name!r}.")


def set_xplane_addon(conn, in_wavefront_file: str = "", in_dict: dict = None):
    """ Set the properties of io_xplane2blender add-on before exporting the mesh to OBJ8 format. """

    if in_dict is None:
        in_dict = {}

    layer_name = os.path.basename(in_wavefront_file)
    print(f'Start set_xplane_addon() for name: {layer_name}')
    print(f'bpy.context.preferences.addons: {type(bpy.context.preferences.addons)}')
    for mod_name in bpy.context.preferences.addons.keys():
        # logger.info(f'\n{datetime.datetime.now()} mod name: {mod_name}')   # Debug
        if "io_xplane2blender" in (mod_name.lower()):
            print(f'FOUND mod: {mod_name}. Will set collection')

            bpy.data.collections["Collection"].xplane.is_exportable_collection = True
            # we define "layer_name" "lit" and "normal" in prepare_texture_names() function
            bpy.data.collections["Collection"].xplane.layer.name = f'{layer_name}_obj8'
            bpy.data.collections["Collection"].xplane.layer.export_type = 'instanced_scenery' # scenery|aircraft|cockpit'
            print(f'xplane.layer.export_type: {bpy.data.collections["Collection"].xplane.layer.export_type}')  # debug
            bpy.data.collections["Collection"].xplane.layer.texture = in_dict["blend_base_texture_name"]
            bpy.data.collections["Collection"].xplane.layer.texture_lit = in_dict["texture_lit"]
            bpy.data.collections["Collection"].xplane.layer.texture_normal = in_dict["texture_normal"]

            bpy.data.scenes["Scene"].xplane.debug = True
            bpy.data.scenes["Scene"].xplane.log = True

            # update DB
            in_binds = [f'{layer_name}_obj8.obj', in_dict.get(K_WAY_ID)]
            in_stmt = f"update {G_OBJ8_DATA_TABLE} set {K_FILE_NAME_OBJ8} = ? where {K_WAY_ID} = ?"
            conn.execute("BEGIN TRANSACTION;")
            exec_stmt(conn, in_stmt, in_binds)
            conn.execute("END TRANSACTION;")

    print("End set_xplane_addon.")


def extract_last_string_with_underscore(input_string, delimiter='/'):
    """ Split a string and return its last split text. Example /path/to/file will return 'file'."""

    # Split the string using "/" as delimiter
    parts = input_string.split(delimiter)

    # Get the last part after splitting
    last_part = parts[-1]

    # Original Test file format looked as follows: "xx_(-3.9762258 137.619211)_331392074" where (xx_({coordinates})_{way_id})
    # If we just want the {way_id} then uncomment the row below
    # Get the last string that starts with "_"
    #  last_part = last_part.split("_")[-1]

    return last_part


def remove_file_extension(file_name):
    """Remove the file string extension. Used when we want to append other string to the file name """
    if file_name.lower().endswith(".obj"):
        return file_name[:-4]  # Remove the last 4 characters (".obj")

    return file_name


def prepare_texture_names(in_dict: {}):
    """Prepare texture info for the material"""
    file_base_name = "blue8x8"
    file_extension = ".png"
    base_path = ""

    if in_dict.get("blend_base_texture_name") is not None and in_dict.get("blend_base_texture_name") != '':
        file_path = in_dict.get("blend_base_texture_name")
        base_path = Path(file_path).parent  # returns the folder path without the name of the file
        file_base_name = Path(file_path).stem
        file_extension = Path(file_path).suffix
    else:
        in_dict["blend_base_texture_name"] = f'{file_base_name}{file_extension}'

    in_dict["layer_name"] = f'{file_base_name}_obj8'
    in_dict["texture_lit"] = f'{base_path}/{file_base_name}_lit{file_extension}'
    in_dict["texture_normal"] = f'{base_path}/{file_base_name}_normal{file_extension}'


def call_external_script(in_file=""):
    """ Call External python script from current script """
    module_name = "uv_manip"
    spec = importlib.util.spec_from_file_location(module_name, in_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    print(f'Executed: {module}.')


def save_as_blend_project(output_base_name):
    """ Save as blender project """
    bpy.ops.wm.save_as_mainfile(filepath=f'{output_base_name}.blend', check_existing=False)


def unwrap_objects():
    """Unwrap the mesh before manually placing them in specific zones, based on the uv_xml_config.xml file."""
    print('START Unwrapping MESH Objects')

    for area in bpy.context.screen.areas:
        print(f'Area Type: {area.type}\t{area}.')
        if area.type in ['VIEW_3D']:
            for local_obj in bpy.context.scene.objects:
                if local_obj.type == 'MESH':  #'MESH':

                    print(f'Unwrapping MESH Object: {local_obj.name}')

                    bpy.context.view_layer.update()
                    # bpy.ops.object.mode_set(mode='OBJECT') # This line fail the script. But I have no idea why 'EDIT' works.
                    bpy.ops.object.select_all(action='DESELECT')
                    local_obj.select_set(True)
                    # Set Active object in layer focus to the obj
                    bpy.context.view_layer.objects.active = local_obj
                    # Enter EDIT mode
                    bpy.ops.object.mode_set(mode='EDIT')
                    # select all faces
                    bpy.ops.mesh.select_all(action='SELECT')
                    # Unwrap
                    # angle_rad  = math.radians(66)
                    # bpy.ops.uv.smart_project(angle_limit=angle_rad)
                    bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)  # Unwrap using angle-based method

                    bpy.ops.object.editmode_toggle()
                    bpy.ops.object.mode_set(mode='OBJECT')

                    print(f"Finish Unwrap MESH: {local_obj.name}")

    print('END Unwrapping MESH Objects')


def exec_stmt(conn, stmt, in_binds=None):
    """Execute SQLite statement"""
    if in_binds is None:
        in_binds = []

    if conn:
        try:
            c = conn.cursor()
            c.execute(stmt, in_binds)
        except Error as stmt_err:
            print(f'{stmt_err}')
            print(f"Stmt: {stmt}\nBinds: {in_binds}")
    else:
        print("Connection is invalid.")
        raise Error('Connection is invalid.')


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
        Array of bind variables. The default is empty array [].

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
        except Error as fetch_err:
            print(fetch_err)
            print(f"Stmt: {stmt}\nBinds: {in_binds}")

    else:
        print("Invalid connection.")
        raise Error("Connection is not valid while fetching data.")

    return None


########################
########################
# MAIN MAIN MAIN #####
########################
########################
CONFIG_BLEND_SAVE_PROJECT = "blend_save_project"
CONFIG_BLEND_EXPORT_VN_FILE = "blend_export_vn_file"
CONFIG_BLEND_EXPORT_XPLANE_OBJ8 = "blend_export_xplane_obj8"
CONFIG_BLEND_EXPORT_XPLANE_OUTPUT_FOLDER = "blend_export_xplane_output_folder"
CONF_OUTPUT_OSM_TO_OBJ_BLEND_LOG_FILENAME = "osm_to_obj_blend_log"  # holds the blender output log file name and path
CONN = None


if __name__ == "__main__":
    # bl_idname = "object.remap_uv"  # Unique identifier for buttons and menu items to reference.
    # bl_label = "MX Remap mesh UV"  # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # Enable undo for the operator.

    logger = logging.getLogger(__name__)
    if len(sys.argv) > 2:
        try:
            # https://blender.stackexchange.com/questions/6817/how-to-pass-command-line-arguments-to-a-blender-python-script
            argv = sys.argv
            argv = argv[argv.index("--") + 1:]  # get all args after "--"

            dc_config = {}
            if len(argv) > 0:
                dc_config = ast.literal_eval(argv[0])

                # logging.basicConfig(filename='osm_to_obj_blend.log', level=logging.INFO, filemode='a')
                logging.basicConfig(filename=dc_config.get(CONF_OUTPUT_OSM_TO_OBJ_BLEND_LOG_FILENAME), level=logging.INFO, filemode='a')
                print(f'argv after --: {argv}')  # debug

                dc_config[CONFIG_BLENDER_VERSION] = int(bpy.app.version[0])

                # Connect to DB
                CONN = sqlite3.connect(dc_config["db_file"])

                # Prepare the texture file names for the material and OBJ8 addon (io_blender2xplane)
                prepare_texture_names(dc_config)

                # logger.info(f'{datetime.datetime.now()} dcConfig:\n{dcConfig}')  # debug
            else:
                raise Error(f'Wrong number of arguments pass to blender.\n{sys.argv}')

            for env in argv[1:]:  # loop over list starting from the second element
                # wavefront_file: str = ""
                if env.endswith(".obj"):
                    print(f'Working on: {env}')
                    # wavefront_file = env
                    import_wavefront(env)
                    print(f'File Imported: {env}')
                    flip_normals()  # This screws the UV Mapping after we manually project them

                    set_material_to_object(dc_config)
                    osm_obj_file_name = remove_file_extension(env)
                    set_xplane_addon(CONN, osm_obj_file_name, dc_config)
                    # Export WaveFront
                    if dc_config.get(CONFIG_BLEND_EXPORT_VN_FILE, False) is True:
                        export_as_obj(osm_obj_file_name)

                    unwrap_objects()  # basic unwrap to all meshes

                    # logger.info(f'{datetime.datetime.now()} Calling external python script.')
                    # call_external_script("blender/uv_manip.py") # deprecate, integrated in current script

                    ###########################
                    # UV Manipulation
                    # Roof and bevel Creation
                    ###########################
                    for obj in bpy.context.scene.objects:
                        if obj.type == 'MESH':
                            print(f'MESH Object: {obj.name}')

                            bpy.context.view_layer.update()

                            bpy.ops.object.mode_set(mode='OBJECT')
                            mesh_dimension = bpy.context.object.dimensions
                            print(f"Mesh dimensions: {mesh_dimension}")
                            # bpy.ops.object.mode_set(mode='EDIT')

                            if bpy.context.object.mode == 'EDIT':
                                print("Marking current object as active.")
                                bpy.ops.object.mode_set(mode='OBJECT')
                                bpy.ops.object.select_all(action='DESELECT')

                            obj.select_set(True)

                            # Set Active object in layer focus to the obj
                            bpy.context.view_layer.objects.active = obj

                            # Enter EDIT mode
                            bpy.ops.object.mode_set(mode='EDIT')

                            print(f"Object mode: {bpy.context.object.mode}")

                            if bpy.context.object.mode == 'EDIT':
                                logger.info('%s RUNNING UV Manipulation', datetime.datetime.now())

                                uv_mapping_based_xml(CONN, obj, dc_config, mesh_dimension)

                            bpy.ops.object.editmode_toggle()
                            bpy.ops.object.mode_set(mode='OBJECT')
                            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

                    if dc_config.get(CONFIG_BLEND_SAVE_PROJECT) is not False:
                        save_as_blend_project(osm_obj_file_name)

                    if dc_config.get(CONFIG_BLEND_EXPORT_XPLANE_OBJ8) is not False:

                        # Export X-Plane OBJ8 format
                        bpy.ops.scene.export_to_relative_dir()

                        # sqlite flow code, "use_sqlite_flow=true"
                        if dc_config.get(CONFIG_USE_SQLITE_FLOW, False):
                            NEW_SEQ = 1
                            WAY_ID = int(dc_config.get(K_WAY_ID, -1))

                            # fetch max sequence number
                            if WAY_ID >= 0:
                                STMT = 'select ifnull( max(seq),0) as max_seq from obj8_data'
                                ROWS = exec_query_stmt(CONN, STMT, [], False)
                                # print (f'{rows}')
                                if ROWS:
                                    NEW_SEQ = int(ROWS['max_seq']) + 1

                                # print (f'New Sequence: {new_seq}.') # debug

                                # fetch same mesh characteristics
                                STMT = """select a.file_name_obj8, b.seq, b.way_id
                                        from obj8_data a, obj8_data b
                                        where a.way_id != b.way_id
                                        and a.edges = b.edges
                                        and a.edges_length = b.edges_length
                                        and a.way_id = ?
                                        and b.seq is not null
                                       """

                                BINDS = [WAY_ID]
                                ROWS = exec_query_stmt(CONN, STMT, BINDS, False)  # fetch only 1 row if exists
                                print(f"{ROWS}")
                                if ROWS is None:
                                    print(f'Did not Found similar mesh for {WAY_ID = }, will get {NEW_SEQ = }.')
                                    BINDS.clear()
                                    STMT = f"update {G_OBJ8_DATA_TABLE} set seq = ? where {K_WAY_ID} = ?"
                                    BINDS = [NEW_SEQ, WAY_ID]
                                    CONN.execute("BEGIN TRANSACTION;")
                                    exec_stmt(CONN, STMT, BINDS)
                                    CONN.execute("END TRANSACTION;")
                                else:
                                    print(f'Found similar mesh for {WAY_ID = }, {ROWS["seq"] = }')
                                    BINDS.clear()
                                    STMT = f'update {G_OBJ8_DATA_TABLE} set similar_to_way_id = ? where {K_WAY_ID} = ?'
                                    BINDS = [int(ROWS[K_WAY_ID]), WAY_ID]
                                    CONN.execute("BEGIN TRANSACTION;")
                                    exec_stmt(CONN, STMT, BINDS)
                                    CONN.execute("END TRANSACTION;")

        except Exception as e:
            logger.info('%s Error:\n{e}', datetime.datetime.now())
        finally:
            if CONN:
                CONN.close()

            logger.info('%s Finish Program.\n', datetime.datetime.now())

# README #

### What is this repository for? ###

* The script should allow you to fetch OSM building data. 
  * It handles the perimeter data from the OSM and guesses heights based on "wall length" which is inaccurate. You can modify the height in blender though.
  * From this information it creates a basic 3D model in WaveFront format that you can modify in Blender. 
  * The 3D mesh will be exported to a folder of your choosing in OBJ8 format for "X-Plane" Custom Scenery use cases.
  * You should modify the "config.json" file to adjust the outcome to your needs.
  * One of the post steps is to create a DSF with all the new ".obj" files configured in it. Unfortunately you will have to import this DSF information into your Custom Scenery in order to see the objects in X-Plane World. 
  

### How do I get set up? ###

The initial configuration was done on a Linux OS, but it was adapted to Windows too:

* Python 3.9 and above (last tested on Python _v3.12_).
* Use git to clone the project, and checkout "develop" or one of the latest feature branches. Your working branch should at least have the following folders:

```
osm_to_xplane
+- tools   (_holds the DSF conversion tools from Laminar Research_)
+- blender (_holds empty blender project + custom blender script_)
```

The output file names are formatted as follows:
* [**mandatory**] Initial WaveFormat file name: "xx_(coordinate)_{way_id}_osm.obj"
* [*optional*] Exported "object" after blender recalculates the object vertices normal: "xx_(coordinate)_{way_id}.vn.obj"  (vn="vertex normal in the file)
* [*optional*] Blender file to edit: "xx_(coordinate)_{way_id}.blend"
  * [dependent on ".blend" file] Exported OBJ8 files: "xx_{coordinate}_{way_id}_osm_obj8.obj"

* Install Blender 3.6x, also tested with Blender v4.2.x
* Make sure you have __read__ and __write__ permissions in the folders you define in the "config.json" file.

### Contribution guidelines ###

* Code review
* The 3D object UV unwrap is done manually for most of the faces. One of the issues we face is that some wrapped "faces" seem to be rotated, so they look upside down.
  * Currently, I try to fix the issue by rotating the "uv face" using: "bpy.ops.mesh.uvs_rotate", but this can only be done using ad-hoc configuration which is a hit and miss, so there are always cases where a texture will be wrongly rotated.
  * If there was away to set all "uv faces" rotation to be the same it might solve the issue (or I'm using here the wrong term). You can follow the following URL to see what I mean: "https://snagardev.weebly.com/blog--news/osm-to-obj-part2".

* If you are proficient with Blender scripting, I'll appreciate if more roof types would be added to the "run_blender_script.py" script. Examples: "https://wiki.openstreetmap.org/wiki/Key:roof:shape" 
* New features should be modifiable through the "_config.json_" file.

### Who do I talk to? ###

* Any ideas/questions can be shared to my e-mail: snagar.dev@protonmail.com

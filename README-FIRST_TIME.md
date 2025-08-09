# README #

Thank you for trying out the python "osm_to_xplane" application.

### Quick Instructions ###
1. modify the "config.json" file (you can use the config_lin/win as a template).
2. Execute:  
```
> $ osm_to_xplane  
```

The longer explanation is down below.

### What is this all about ? What it does and don't ###

### What the program does ###
* The application should allow you to fetch OSM building data. 
* It only handles the perimeter data from the OSM and guesses heights based on "wall length" which is inaccurate. You can modify the height in blender though for specific buildings.
* From the osm information it creates a basic 3D model in WaveFront format that you can modify in Blender.
* The blender script will prepare the mesh to be X-Plane ready, which also includes the texture mapping. This process is not accurate without correctly defining the texture sub parts in the "[uv_xml_config.xml](uv_xml_config.xml)" file.   
* If you correctly defined the "[config.json](config.json)" file, it can auto exports the ".obj" files to a folder of your choosing in OBJ8 format for "X-Plane" Custom Scenery use cases.
* You should modify the "config.json" file to adjust the outcome to your needs.
* The application will prepare a DSF file using DSF2Text file that you should import into WED in order to see the new ".obj" meshes in X-Plane.

### What the program does not do ###  
* UV unwrapping is a challenge by itself, the program does a basic texturing and unwrapping to specific faces (top face = roof).
* You have to correctly re-map your texture in the "[uv_xml_config.xml](uv_xml_config.xml)" file, so the outcome will be plausible, and even then there will probably be flipped textures.
* Although the program creates a custom DSF with the new "obj" files locations in it, You will have to manually import it into WED.

### What are the prerequisites ###

The initial configuration was done on a Linux OS, but it was adapted to Windows too:
* You have to prepare a config.json file with your settings. Please check the "config.template.json" file and the demo config_{os}.json examples.
* Blender 3.6x (Should work on Blender 4.2.x too)
* Make sure you have read and write permissions on the folders you defined in the "config.json" file.


### Step-by-Step instructions - For beginners ###
Before starting, consider watching the tutorial video: https://youtu.be/H3M_I2AtAsM

Use "[overpass turbo](https://overpass-turbo.eu/)" site to gather metadata information of your "area of interest" (bbox, metadata and if there are enough building data).

1. create a "config.json" file from one of the templates.
2. Edit the "config.json" file and fill in the following attributes: "osm_bbox, script_work_folder, blender_bin, limit, root_scenery_folder_to_copy_obj8_files"
3. If you are new to this program, carefully read the attributes' description.
4. If you start a new scenery with a new area, update the "**limit**" attribute to a small value. Raise it to a two-digit number if the process seem to work correctly.
   * Remember: The script counts "_processed_" and "_skipped_" buildings as part of the "_limit_" rule. 
5. After a short test, open one or more "_.blend_" files and inspect the 3D mesh to verify nothing is out of the ordinary (the texture might be missing if you did not define one).
6. Set up a texture file with "_roof, walls_" (should be mandatory) and "windows and doors" (optional).
7. Modify the "**_uv_xml_config.xml_**" file to reflect the different "_set_" of textures tiles. Since v2024.11.0, there are more options to distinguish between building types, using the "metadata" output.
8. Run tests on a few buildings to test the texture mapping. Once result looks promising, you can run this on a bigger area of interest.
9. Open WED and import the DSF that was created (usually in the "osm_to_xplane/tools" subfolder).
10. If all is well, update the "**limit**" attribute, you can now run the program on the final set of buildings (largest number).
11. **Tip**: you can enable the attribute: "**skip_rule**: 5" (was _"resume_rule"_) so next run, the program will skip already processed buildings.
12. **Tip**: You can filter the size of houses by enabling and updating the "_filter_" options in the "config.json" file.

Now that the config file is set, you can execute the script:
```
> $ osm_to_xplane  
```

### Who do I talk to? ###

* Any ideas/questions can be shared to my e-mail: snagar.dev@protonmail.com

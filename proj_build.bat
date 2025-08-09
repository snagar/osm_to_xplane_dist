@REM ## Step 1: pack the project
echo "Packing Python Project"
echo " "
pyinstaller --clean --noconfirm osm_to_xplane.py

@REM ## Step 2: Copy the needed files into the project
echo " "
echo "Post Pack - Copying the missing files"

@REM # Copy mandatory files
copy   README-FIRST_TIME.md dist\\osm_to_xplane\\
copy   README-FIRST_TIME.md dist\\osm_to_xplane\\README-FIRST-TIME.txt
copy   config*.json dist\\osm_to_xplane\\
del /Q /F dist\\osm_to_xplane\\config.json
copy   uv_xml_config.xml dist\\osm_to_xplane\\
copy   dsf_template.tmpl dist\\osm_to_xplane\\
@REM # Copy folders
xcopy /EY  tools dist\\osm_to_xplane\\tools\\
xcopy /EY  blender dist\\osm_to_xplane\\blender\\
xcopy /EY  textures dist\\osm_to_xplane\\textures\\


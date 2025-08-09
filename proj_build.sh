#!/bin/bash

source .venv/bin/activate

## Create the destination folder
mkdir -p dist/osm_to_xplane/

## Step 1: pack the project
echo -e "\n\nPacking Python Project\n"

if [ -z "$VIRTUAL_ENV_PROMPT" ]; then
    echo -e "no value is set for environment variable: \$VIRTUAL_ENV_PROMPT\n"
    pyinstaller --clean --noconfirm osm_to_xplane.py
else
    echo "VIRTUAL_ENV_PROMPT is set to: $VIRTUAL_ENV_PROMPT"
    "$VIRTUAL_ENV_PROMPT/bin/pyinstaller" --clean --noconfirm osm_to_xplane.py
fi


## Step 2: Copy the needed files into the project
echo -e "\nPost Pack - Copying the missing files\n"

# Copy mandatory files
cp -p README-FIRST_TIME.md dist/osm_to_xplane/
cp -p README-FIRST_TIME.md dist/osm_to_xplane/README-FIRST-TIME.txt
cp -p config*.json dist/osm_to_xplane/
rm -f dist/osm_to_xplane/config.json
cp -p uv_xml_config.xml dist/osm_to_xplane/
cp -p dsf_template.tmpl dist/osm_to_xplane/

# Copy folders and clean them
echo -e "\nCopy folders and clean them.\n"
cp -rp tools dist/osm_to_xplane
rm -f  dist/osm_to_xplane/tools/dsf_obj8*

cp -rp blender dist/osm_to_xplane/
cp -rp textures dist/osm_to_xplane/

exit 0;
